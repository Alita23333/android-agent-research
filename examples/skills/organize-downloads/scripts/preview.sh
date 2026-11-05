download_dir="/sdcard/Download"
find "$download_dir" -maxdepth 1 -type f -print 2>/dev/null | while IFS= read -r file; do
  name="${file##*/}"
  ext="${name##*.}"
  lower="$(printf '%s' "$ext" | tr '[:upper:]' '[:lower:]')"
  case "$lower" in
    jpg|jpeg|png|gif|webp|heic) category="Images" ;;
    mp4|mkv|mov|webm) category="Videos" ;;
    mp3|flac|wav|m4a|ogg) category="Audio" ;;
    pdf|doc|docx|xls|xlsx|ppt|pptx|txt|md) category="Documents" ;;
    zip|7z|rar|tar|gz|apk) category="Archives" ;;
    *) category="Other" ;;
  esac
  printf '%s\t%s\n' "$category" "$name"
done
