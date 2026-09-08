CORTANA 4.0 - proyecto funcional Windows

Requisitos:
- Python 3.11/3.12
- Ollama instalado y un modelo local, por defecto qwen2.5:7b
- pip install -r requirements.txt

Ejecutar:
python main.py

Acciones funcionales incluidas:
- crear carpetas en Escritorio
- abrir/cerrar programas comunes
- buscar en Google/YouTube
- multimedia y volumen
- apagar/reiniciar/cancelar apagado con confirmación
- desinstalar por winget con confirmación
- abrir configuración de contraseña de Windows
- aprendizaje persistente con primera confirmación y segunda confirmación
- conversación de contexto durante confirmaciones

Las habilidades generadas por IA pasan por una validación que bloquea comandos destructivos/arbitrarios.
