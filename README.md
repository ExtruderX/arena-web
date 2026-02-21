# Arena (pygame) -> Web (iPad) Build

Bu repo, oyunu tarayıcıda (iPad/Safari dahil) çalıştırmak için **pygbag** (pygame->WebAssembly) kullanır.

## Kontroller (iPad)
Bu oyun klavye/mouse mantığında yazıldı:
- En iyi deneyim: iPad'e Bluetooth klavye + mouse/trackpad veya gamepad bağla.
- Dokunmatik (touch) için sanal joystick/btn eklemek istersen ayrıca yaparız.

## Lokal test (PC/Mac)
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/main.py
```

## Web (lokal) test
```bash
python -m pygbag src/main.py
# tarayıcı: http://localhost:8000
```

## GitHub Pages ile ücretsiz yayın (en kolay)
1) Bu repoyu GitHub'a `main` branch olarak push et.
2) GitHub'da: **Settings -> Pages**
   - Source: **Deploy from a branch**
   - Branch: **gh-pages** / /(root)
3) Push yaptıktan sonra Actions otomatik:
   - pygbag ile build alır
   - `src/build/web` içeriğini `gh-pages` branch'ine deploy eder
4) URL: `https://<kullanici>.github.io/<repo>/`

## iPad'e "app gibi" ekleme (PWA benzeri)
- Safari'de oyunun URL'sini aç
- Share (Paylaş) -> **Add to Home Screen**
- Böylece tam ekrana yakın, bağımsız ikonla açılır.

## Save sistemi
Web'de `save.json` yerine **localStorage** kullanır (anahtar: `arena_save_v7`).
Desktop'ta dosya olarak `src/save.json` benzeri davranır.
