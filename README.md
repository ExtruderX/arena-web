# Arena WebApp (iPad/Safari)

Bu proje `pygbag` ile pygame oyununu WebAssembly olarak derleyip GitHub Pages'te yayınlamak için hazırlanmıştır.

## GitHub'a yükleme (UI ile, en sorunsuz yöntem)

1) GitHub'da yeni repo aç (Public).
2) Bu zip'i çıkar.
3) Repo -> Add file -> Upload files:
   - `src/` klasörünü yükle (sadece bu yeterli).
4) `.github` klasörünü upload etmeye çalışma (GitHub "hidden file" hatası verebiliyor).

## Workflow dosyasını GitHub içinde oluştur

Repo -> Add file -> Create new file

Dosya adı:
`.github/workflows/deploy.yml`

İçerik: `workflow_deploy.yml.txt` dosyasının içini kopyalayıp yapıştır.

Commit et.

## Actions izinleri

Settings -> Actions -> General -> Workflow permissions:
`Read and write permissions` seç -> Save

## Pages ayarı

Settings -> Pages:
Source: Deploy from a branch
Branch: gh-pages / (root)

Site URL:
https://KULLANICIADI.github.io/REPOADI/

## Save sistemi

- Desktop'ta `save.json`
- Web'de tarayıcı `localStorage` (SAVE_KEY: arena_save_v7)
