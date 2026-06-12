# Shipworks demo UI

A one-file storefront ([index.html](index.html)) that POSTs an order to the
buggy-service Lambda — the browser-friendly replacement for the `curl` demo.

- **Guest checkout** toggle on → sends `{"customer": null}` → 500, and an
  incident is logged (Patchwork opens a fix PR behind the scenes).
- Toggle off → a normal order → 200 with a shipping quote.

## Run

```bash
cd web
python3 -m http.server 8000
# open http://localhost:8000
```

(Serving over `http://` is more reliable than opening the file directly —
some browsers send a `null` Origin for `file://`.)

## One-time: enable CORS on the Lambda

The browser enforces CORS; `curl` doesn't. Configure the Function URL once so
the page can call it:

```bash
aws lambda update-function-url-config \
  --function-name buggy-service --region us-west-2 \
  --cors '{"AllowOrigins":["*"],"AllowMethods":["POST"],"AllowHeaders":["content-type"]}'
```

`AllowOrigins: ["*"]` is fine for a local demo. For anything real, restrict it
to your actual origin (e.g. `http://localhost:8000`).

## Point it at your Lambda

The Function URL is hardcoded near the top of [index.html](index.html) as
`LAMBDA_URL`. Change it if your endpoint differs.
