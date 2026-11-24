"""Evaluación integral y reproducible de UMA MUSUME ChatBot v3.0.

Evalúa tres dimensiones verificables: clasificación en conjuntos existentes,
política de confianza y regresión conversacional, y latencia de consola/API.
Genera resultados JSON/CSV/Markdown sin entrenar ni modificar el modelo.
IMPORTANTE: los conjuntos de prueba ya se usaron anteriormente; sus resultados
no constituyen una nueva prueba ciega. La calidad estratégica requiere jueces.

Ejecutar desde la raíz del proyecto:
    python -m src.evaluation.evaluacion_integral --modelo v3
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score

from src.conversation.confidence_manager import ConfidenceManager
from src.conversation.dialogue_manager import DialogueManager
from src.conversation.knowledge_base import normalizar
from src.models.predictor_adapter import construir_predictor

RAIZ = Path(__file__).resolve().parents[2]
MODELOS = {
    "original": "mejor_modelo.joblib",
    "reforzado": "modelo_reforzado_etapa3.joblib",
    "v3": "modelo_v3.joblib",
}


def percentil_95(valores: list[float]) -> float | None:
    """Calcula el percentil 95 de una lista de tiempos, en milisegundos."""
    return round(float(np.percentile(valores, 95)), 3) if valores else None


def evaluar_clasificador(predictor: Any, ruta: Path, salida: Path, etiqueta: str) -> dict:
    """Evalúa un dataset histórico etiquetado y exporta errores y matriz de confusión.

    No utiliza las etiquetas para modificar pesos, hiperparámetros ni umbrales.
    La medida puede estar afectada por evaluaciones anteriores del equipo.
    """
    datos = pd.read_csv(ruta).dropna(subset=["texto", "intencion"])
    reales = datos["intencion"].astype(str).tolist()
    textos = datos["texto"].astype(str).tolist()
    modelo = predictor.modelo
    tiempos = []
    predicciones = []
    probabilidades = []
    for mensaje in textos:
        inicio = time.perf_counter()
        proba = modelo.predict_proba([mensaje])[0]
        tiempos.append((time.perf_counter() - inicio) * 1000)
        probabilidades.append(proba)
        predicciones.append(str(modelo.classes_[int(np.argmax(proba))]))
    matriz_probas = np.asarray(probabilidades)
    orden = np.argsort(-matriz_probas, axis=1)
    indices = {nombre: i for i, nombre in enumerate(modelo.classes_)}
    top3 = sum(indices.get(y, -1) in set(orden[i, :3]) for i, y in enumerate(reales)) / len(reales)
    etiquetas = sorted(set(reales) | set(predicciones))
    cm = confusion_matrix(reales, predicciones, labels=etiquetas)
    pd.DataFrame(cm, index=etiquetas, columns=etiquetas).to_csv(salida / f"matriz_{etiqueta}.csv", encoding="utf-8-sig")
    informe = classification_report(reales, predicciones, labels=etiquetas, output_dict=True, zero_division=0)
    pd.DataFrame(informe).T.to_csv(salida / f"reporte_clases_{etiqueta}.csv", encoding="utf-8-sig")
    detalles = pd.DataFrame({
        "texto": textos, "real": reales, "predicha": predicciones,
        "confianza": matriz_probas.max(axis=1),
        "segunda": [str(modelo.classes_[int(row[1])]) for row in orden],
        "margen": [float(np.sort(row)[-1] - np.sort(row)[-2]) for row in matriz_probas],
        "correcta": [a == b for a, b in zip(reales, predicciones)],
    })
    detalles[~detalles["correcta"]].to_csv(salida / f"errores_{etiqueta}.csv", index=False, encoding="utf-8-sig")
    return {
        "archivo": str(ruta.relative_to(RAIZ)), "muestras": len(reales),
        "accuracy": round(accuracy_score(reales, predicciones), 5),
        "precision_macro": round(precision_score(reales, predicciones, average="macro", zero_division=0), 5),
        "recall_macro": round(recall_score(reales, predicciones, average="macro", zero_division=0), 5),
        "f1_macro": round(f1_score(reales, predicciones, average="macro", zero_division=0), 5),
        "top3_accuracy": round(top3, 5),
        "latencia_predict_ms_p50": round(statistics.median(tiempos), 3),
        "latencia_predict_ms_p95": percentil_95(tiempos),
        "errores": int(sum(a != b for a, b in zip(reales, predicciones))),
    }


def evaluar_confianza(predictor: Any, ruta: Path, salida: Path) -> dict:
    """Mide cobertura y exactitud selectiva en un conjunto ya conocido.

    Separa tres acciones (aceptar/aclarar/reformular); no interpreta las
    aclaraciones como exitosas ni recalibra los umbrales con estas etiquetas.
    """
    politica = ConfidenceManager()
    datos = pd.read_csv(ruta).dropna(subset=["texto", "intencion"])
    registros = []
    for fila in datos.itertuples(index=False):
        candidatos = predictor.top_k(str(fila.texto), 3)
        decision = politica.evaluar(candidatos)
        registros.append({
            "texto": fila.texto, "real": fila.intencion,
            "predicha": candidatos[0][0], "confianza": candidatos[0][1],
            "margen": decision["margen"], "accion": decision["accion"],
            "correcta": candidatos[0][0] == fila.intencion,
        })
    tabla = pd.DataFrame(registros)
    tabla.to_csv(salida / "decisiones_confianza.csv", index=False, encoding="utf-8-sig")
    aceptadas = tabla[tabla["accion"] == "aceptar"]
    return {
        "muestras": len(tabla),
        "acciones": {accion: int((tabla["accion"] == accion).sum()) for accion in ("aceptar", "aclarar", "reformular")},
        "cobertura": round(len(aceptadas) / len(tabla), 5),
        "precision_selectiva": round(float(aceptadas["correcta"].mean()), 5) if len(aceptadas) else None,
        "errores_aceptados": int((~aceptadas["correcta"]).sum()) if len(aceptadas) else 0,
        "nota": "Mide la decisión inicial, NO el éxito de aclaraciones posteriores.",
    }


def comprobar_paso(paso: dict, resultado: dict) -> list[str]:
    """Compara un turno real contra la expectativa declarada en JSON."""
    errores = []
    if resultado["intencion"] != paso["intencion"]:
        errores.append(f"Intención: {resultado['intencion']} != {paso['intencion']}")
    texto = normalizar(resultado["respuesta"])
    contenidos = [normalizar(x) for x in paso.get("contiene", [])]
    if contenidos and not (any(s in texto for s in contenidos) if paso.get("alguna") else all(s in texto for s in contenidos)):
        errores.append("Contenido requerido ausente")
    if any(normalizar(x) in texto for x in paso.get("no_contiene", [])):
        errores.append("Aparece contenido prohibido")
    for campo, esperado in paso.get("slots", {}).items():
        if resultado["contexto"]["slots"].get(campo) != esperado:
            errores.append(f"Slot {campo} incorrecto")
    if "fuente" in paso and resultado["fuente"] != paso["fuente"]:
        errores.append("Fuente incorrecta")
    return errores


def evaluar_dialogos(predictor: Any, salida: Path) -> dict:
    """Ejecuta escenarios de regresión preexistentes y registra fallos por turno.

    Cada conversación usa un gestor reiniciado y semilla fija. Los casos no
    constituyen un banco ciego ni una evaluación de calidad humana.
    """
    casos = json.loads((RAIZ / "tests" / "conversation_tests.json").read_text(encoding="utf-8"))
    manager = DialogueManager(predictor, RAIZ / "data" / "game", seed=0)
    registros = []
    tiempos = []
    completos = 0
    for caso in casos:
        manager.reiniciar()
        errores_caso = 0
        for indice, paso in enumerate(caso["pasos"], 1):
            inicio = time.perf_counter()
            respuesta = manager.responder(paso["usuario"])
            duracion = (time.perf_counter() - inicio) * 1000
            tiempos.append(duracion)
            errores = comprobar_paso(paso, respuesta)
            errores_caso += bool(errores)
            registros.append({
                "conversacion": caso["nombre"], "turno": indice, "mensaje": paso["usuario"],
                "intencion_obtenida": respuesta["intencion"], "fuente": respuesta["fuente"],
                "correcto": not errores, "errores": "; ".join(errores),
                "latencia_ms": round(duracion, 3),
            })
        completos += int(errores_caso == 0)
    pd.DataFrame(registros).to_csv(salida / "turnos_conversacionales.csv", index=False, encoding="utf-8-sig")
    return {
        "escenarios": len(casos), "escenarios_completados": completos,
        "tasa_exito_escenario": round(completos / len(casos), 5),
        "turnos": len(registros), "turnos_correctos": sum(x["correcto"] for x in registros),
        "tasa_exito_turno": round(sum(x["correcto"] for x in registros) / len(registros), 5),
        "latencia_dialogo_ms_p50": round(statistics.median(tiempos), 3),
        "latencia_dialogo_ms_p95": percentil_95(tiempos),
    }


def evaluar_api(salida: Path, repeticiones: int = 25) -> dict:
    """Mide latencia de solicitudes HTTP locales mediante TestClient.

    Las mediciones son orientativas, sin red ni concurrencia real; se reinicia
    el contexto creando nuevas sesiones para no confundir memoria con rapidez.
    """
    from fastapi.testclient import TestClient
    from src.api import app as modulo

    tiempos = []
    estados = []
    with TestClient(modulo.build_app()) as cliente:
        salud = cliente.get("/api/health")
        for _ in range(repeticiones):
            inicio = time.perf_counter()
            resultado = cliente.post("/api/chat", json={"mensaje": "¿Para qué sirve Stamina?"})
            tiempos.append((time.perf_counter() - inicio) * 1000)
            estados.append(resultado.status_code)
    return {
        "salud_http": salud.status_code, "modelo_reportado": salud.json().get("modelo"),
        "peticiones": repeticiones, "respuestas_http_200": estados.count(200),
        "latencia_api_local_ms_p50": round(statistics.median(tiempos), 3),
        "latencia_api_local_ms_p95": percentil_95(tiempos),
        "advertencia": "TestClient en el mismo proceso; no representa latencia de red ni carga multiusuario.",
    }


def crear_rubrica(salida: Path) -> None:
    """Crea plantilla en blanco para evaluación humana, sin inventar calificaciones."""
    destino = salida / "rubrica_evaluacion_humana.csv"
    campos = ["evaluador", "fecha", "id_conversacion", "turno", "pregunta", "respuesta",
              "exactitud_factual_1a5", "relevancia_1a5", "contexto_1a5",
              "claridad_1a5", "utilidad_1a5", "observaciones", "fuente_verificada"]
    with destino.open("w", newline="", encoding="utf-8-sig") as archivo:
        csv.writer(archivo).writerow(campos)


def escribir_resumen(resultados: dict, salida: Path) -> None:
    """Genera un resumen Markdown que distingue resultados y limitaciones."""
    lines = ["# Etapa 6 — Resultados de evaluación integral", "",
             f"Generado (UTC): {resultados['fecha_utc']}", "",
             "**Importante:** los datasets y escenarios provienen de etapas previas. No son pruebas ciegas nuevas.", "",
             "## Clasificación", "",
             "| Conjunto | Muestras | Accuracy | F1 macro | Top-3 | Errores |", "|---|---:|---:|---:|---:|---:|"]
    for key, r in resultados["clasificacion"].items():
        lines.append(f"| {key} | {r['muestras']} | {r['accuracy']:.2%} | {r['f1_macro']:.2%} | {r['top3_accuracy']:.2%} | {r['errores']} |")
    c = resultados["confianza"]
    d = resultados["conversaciones"]
    a = resultados.get("api")
    lines += ["", "## Confianza (medición retrospectiva)", "",
              f"Cobertura: **{c['cobertura']:.2%}**. Exactitud entre aceptadas: **{c['precision_selectiva']:.2%}**." if c["precision_selectiva"] is not None else "Sin aceptaciones.",
              f"Decisiones: {c['acciones']}. Errores aceptados: {c['errores_aceptados']}.", "",
              "## Conversaciones de regresión", "",
              f"Escenarios completos: **{d['escenarios_completados']}/{d['escenarios']}**; turnos correctos: **{d['turnos_correctos']}/{d['turnos']}**.",
              f"Latencia del diálogo p50/p95: {d['latencia_dialogo_ms_p50']} / {d['latencia_dialogo_ms_p95']} ms.", ""]
    if a:
        lines += ["## API local", "",
                  f"HTTP 200: **{a['respuestas_http_200']}/{a['peticiones']}**; latencia p50/p95: {a['latencia_api_local_ms_p50']} / {a['latencia_api_local_ms_p95']} ms.", ""]
    lines += ["## Pendiente de evaluación humana", "",
              "La rúbrica `rubrica_evaluacion_humana.csv` está vacía. No atribuir puntuaciones de calidad factual, utilidad, claridad o experiencia de usuario hasta que evaluadores la completen.", "",
              "## Alcance y limitaciones", "",
              "- No se reentrenó ni recalibró ningún modelo durante esta etapa.",
              "- No se ajustaron umbrales con la prueba.",
              "- Los experimentos de clasificación y diálogo no son una prueba independiente nueva.",
              "- La latencia de API proviene de TestClient local, no de usuarios reales.",
              "- La recomendación de cartas debe validarse con fuentes del juego y personas conocedoras.", ""]
    (salida / "RESUMEN_RESULTADOS.md").write_text("\n".join(lines), encoding="utf-8")


def ejecutar(modelo: str = "v3", repeticiones_api: int = 25, incluir_api: bool = True) -> dict:
    """Orquesta todas las mediciones y conserva resultados con nombre de modelo."""
    destino = RAIZ / "data" / "processed" / "etapa6" / modelo
    destino.mkdir(parents=True, exist_ok=True)
    predictor = construir_predictor(RAIZ / "artifacts" / MODELOS[modelo])
    clasificacion = {
        "dbc_v3_test_historico": evaluar_clasificador(predictor, RAIZ / "data" / "raw" / "test.csv", destino, "dbc_v3"),
        "challenge_etapa3_historico": evaluar_clasificador(predictor, RAIZ / "data" / "challenge" / "evaluacion_nueva_v1.csv", destino, "challenge"),
    }
    resultados = {
        "fecha_utc": datetime.now(timezone.utc).isoformat(), "modelo": modelo,
        "clasificacion": clasificacion,
        "confianza": evaluar_confianza(predictor, RAIZ / "data" / "challenge" / "evaluacion_nueva_v1.csv", destino),
        "conversaciones": evaluar_dialogos(predictor, destino),
        "api": evaluar_api(destino, repeticiones_api) if incluir_api else None,
    }
    crear_rubrica(destino)
    (destino / "resultados.json").write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
    escribir_resumen(resultados, destino)
    return resultados


def main() -> None:
    """Procesa los argumentos de la terminal y muestra las métricas principales."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", choices=MODELOS.keys(), default="v3")
    parser.add_argument("--sin-api", action="store_true", help="Omite pruebas HTTP locales")
    parser.add_argument("--peticiones", type=int, default=25, help="Número de solicitudes HTTP locales")
    args = parser.parse_args()
    if args.peticiones < 1:
        parser.error("--peticiones debe ser positivo")
    r = ejecutar(args.modelo, args.peticiones, not args.sin_api)
    print(json.dumps({"modelo": r["modelo"], "clasificacion": r["clasificacion"],
                      "confianza": r["confianza"], "conversaciones": r["conversaciones"],
                      "api": r["api"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
