# Rastreador Celular Web

Sistema simples de rastreamento de celular via navegador.

## Deploy rápido no Render (grátis)

1. Vá em https://render.com
2. New → Web Service
3. Conecte este repositório
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn app:app`
6. Deploy

O QR Code no mapa aponta automaticamente para a URL do Render.

## Rodar local

```bash
pip install -r requirements.txt
python app.py
```

- Mapa: http://localhost:5000
- Celular: http://localhost:5000/track
