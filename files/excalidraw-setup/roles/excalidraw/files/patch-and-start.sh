#!/bin/sh
set -e

if [ -n "$BACKEND_URL" ]; then
  # Find the bundle file that contains the hardcoded storage backend URLs
  JS=$(grep -rl 'json.excalidraw.com' /usr/share/nginx/html/assets/ 2>/dev/null | grep -v '\.map$' | head -1)
  if [ -n "$JS" ]; then
    # POST URL — replace first (more specific, includes /post/ suffix)
    sed -i \
      "s|https://json.excalidraw.com/api/v2/post/|${BACKEND_URL}/api/v2/scenes|g" \
      "$JS"
    # GET base URL — replace second to avoid clobbering the POST match
    sed -i \
      "s|https://json.excalidraw.com/api/v2/|${BACKEND_URL}/api/v2/scenes/|g" \
      "$JS"
  fi
fi

exec nginx -g "daemon off;"
