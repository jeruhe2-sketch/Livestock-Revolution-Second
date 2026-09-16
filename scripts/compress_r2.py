import subprocess, os, sys, tempfile, shutil
from PIL import Image

MAX_DIM = 1600       # 긴 변 기준 최대 픽셀
JPEG_QUALITY = 82
BUCKET = "livestock-library"

def main():
    endpoint = os.environ['R2_ENDPOINT']
    workdir = tempfile.mkdtemp()
    local_dir = os.path.join(workdir, "bucket")

    print(f"1) 버킷 전체 다운로드 -> {local_dir}", flush=True)
    subprocess.run([
        "aws", "s3", "sync", f"s3://{BUCKET}/", local_dir,
        "--endpoint-url", endpoint, "--profile", "r2"
    ], check=True)

    total = 0
    resized = 0
    before_bytes = 0
    after_bytes = 0

    for root, _, files in os.walk(local_dir):
        for fname in files:
            path = os.path.join(root, fname)
            ext = fname.lower().rsplit('.', 1)[-1] if '.' in fname else ''
            if ext not in ('jpg', 'jpeg', 'png', 'webp'):
                continue
            total += 1
            try:
                orig_size = os.path.getsize(path)
                before_bytes += orig_size
                with Image.open(path) as img:
                    img_format = img.format  # JPEG or PNG
                    w, h = img.size
                    scale = MAX_DIM / max(w, h)
                    changed = False
                    if scale < 1:
                        new_size = (int(w * scale), int(h * scale))
                        img = img.resize(new_size, Image.LANCZOS)
                        changed = True

                    if img_format == 'JPEG' or ext in ('jpg', 'jpeg'):
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        img.save(path, 'JPEG', quality=JPEG_QUALITY, optimize=True)
                        changed = True
                    elif img_format == 'PNG' or ext == 'png':
                        img.save(path, 'PNG', optimize=True)
                        changed = True
                    elif img_format == 'WEBP' or ext == 'webp':
                        if img.mode not in ('RGB', 'RGBA'):
                            img = img.convert('RGB')
                        img.save(path, 'WEBP', quality=JPEG_QUALITY)
                        changed = True

                new_size_bytes = os.path.getsize(path)
                after_bytes += new_size_bytes
                if changed:
                    resized += 1
                print(f"  {fname}: {orig_size//1024}KB -> {new_size_bytes//1024}KB", flush=True)
            except Exception as e:
                print(f"  !! 실패 {fname}: {e}", flush=True)
                after_bytes += os.path.getsize(path)

    print(f"\n2) 처리 완료: {total}개 중 {resized}개 리사이즈/재압축", flush=True)
    print(f"   전체 용량: {before_bytes/1024/1024:.1f}MB -> {after_bytes/1024/1024:.1f}MB", flush=True)

    print("3) 압축된 파일 R2에 재업로드", flush=True)
    subprocess.run([
        "aws", "s3", "sync", local_dir, f"s3://{BUCKET}/",
        "--endpoint-url", endpoint, "--profile", "r2"
    ], check=True)

    shutil.rmtree(workdir, ignore_errors=True)
    print("완료", flush=True)

if __name__ == "__main__":
    main()
