@echo off
:: --- Configuración ---
set URL=http://localhost:8080/ai/chat-stream
set HEADER=Content-Type: application/json

:: --- Pregunta (puedes cambiar el texto entre comillas) ---
set MESSAGE=Hola Gemini, dame 3 ideas para mejorar la rentabilidad de mi negocio

:: --- Ejecutar petición con cURL ---
echo Enviando a %URL%...
curl -N -X POST %URL% ^
  -H "%HEADER%" ^
  -d "{\"messages\":[{\"role\":\"user\",\"content\":\"%MESSAGE%\"}]}"

echo.
echo --- Fin de la respuesta ---
pause
