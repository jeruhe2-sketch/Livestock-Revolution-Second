import subprocess, os, tempfile, shutil
from PIL import Image

THUMB_MAX_DIM = 400   # 그리드용 썸네일 최대 변
THUMB_QUALITY = 70
BUCKET = "livestock-library"

def main():
    endpoint = os.environ['R2_ENDPOINT']
    workdir = tempfile.mkdtemp()
    local_dir = os.path.join(workdir, "bucket")
    thumb_dir = os.path.join(workdir, "thumbs")

    print("1) 원본 버킷 다운로드", flush=True)
    subprocess.run([
        "aws", "s3", "sync", f"s3://{BUCKET}/", local_dir,
        "--endpoint-url", endpoint, "--profile", "r2",
        "--exclude", "thumbs/*"
    ], check=True)

    count = 0
    for root, _, files in os.walk(local_dir):
        if os.path.commonpath([root, thumb_dir]) == thumb_dir:
            continue
        for fname in files:
            path = os.path.join(root, fname)
            ext = fname.lower().rsplit('.', 1)[-1] if '.' in fname else ''
            if ext not in ('jpg', 'jpeg', 'png', 'webp'):
                continue
            rel = os.path.relpath(path, local_dir)
            thumb_name = rel.rsplit('.', 1)[0] + '.jpg'  # 썸네일은 전부 jpg로 통일
            thumb_path = os.path.join(thumb_dir, thumb_name)
            os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
            try:
                with Image.open(path) as img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    w, h = img.size
                    scale = THUMB_MAX_DIM / max(w, h)
                    if scale < 1:
                        img = img.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
                    img.save(thumb_path, 'JPEG', quality=THUMB_QUALITY, optimize=True)
                count += 1
                if count % 20 == 0:
                    print(f"  {count}개 처리...", flush=True)
            except Exception as e:
                print(f"  !! 실패 {rel}: {e}", flush=True)

    print(f"2) 썸네일 {count}개 생성 완료, 업로드 중", flush=True)
    subprocess.run([
        "aws", "s3", "sync", thumb_dir, f"s3://{BUCKET}/thumbs/",
        "--endpoint-url", endpoint, "--profile", "r2"
    ], check=True)

    shutil.rmtree(workdir, ignore_errors=True)
    print("완료", flush=True)

if __name__ == "__main__":
    main()
