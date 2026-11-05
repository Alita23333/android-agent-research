#!/system/bin/sh
initialized=false
while IFS= read -r request; do
  id="$(printf '%s' "$request" | sed -n 's/.*"id"[ ]*:[ ]*\([0-9][0-9]*\).*/\1/p')"
  if [ "$initialized" = false ]; then
    printf '%s\n' "{\"jsonrpc\":\"2.0\",\"id\":$id,\"result\":{\"protocolVersion\":\"1.0\",\"tools\":[{\"name\":\"identity\",\"version\":\"1.0.0\",\"description\":\"Read Android brand, model, ABI and API level through an APK-owned local provider process.\",\"inputSchema\":{\"type\":\"object\",\"properties\":{},\"additionalProperties\":false},\"capabilities\":[\"device-read\"],\"sideEffect\":\"NONE\",\"supportsCancellation\":false}]}}"
    initialized=true
  else
    brand="$(getprop ro.product.brand)"
    model="$(getprop ro.product.model)"
    abi="$(getprop ro.product.cpu.abi)"
    api="$(getprop ro.build.version.sdk)"
    printf '%s\n' "{\"jsonrpc\":\"2.0\",\"id\":$id,\"result\":{\"ok\":true,\"data\":{\"brand\":\"$brand\",\"model\":\"$model\",\"abi\":\"$abi\",\"api\":\"$api\"}}}"
  fi
done
