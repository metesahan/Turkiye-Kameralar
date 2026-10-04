# CLAUDE.md — Türkiye Kameraları

Bu dosya, projede çalışacak Claude'a (Claude Code veya claude.ai) bağlam verir. Genel tanıtım için `README.md` dosyasına bakın.

## Proje özeti

PyQt6 masaüstü uygulaması. İBB'nin HLS kameralarını OpenCV ile okur. Ultralytics YOLO11s ile tespit, `trackers` kütüphanesindeki BoT-SORT ile takip, OpenCV TrackerVit ile hedef kilitleme yapar. Hava durumu Open-Meteo'dan gelir. macOS (MPS) ve Windows (CUDA) hedeflenir. PyInstaller ile `.app` / `.exe` olarak paketlenir.

Geliştirici: Mete Şahan. Arayüz dili Türkçe.

## Komutlar

```bash
.venv/bin/python main.py                       # çalıştır
TK_DEBUG=1 .venv/bin/python main.py            # yapay zekâ durumu ve tespitleri terminale yaz
.venv/bin/python -m pyflakes turkiye_kameralari main.py   # statik kontrol
./build_mac.sh                                 # Türkiye Kameraları.app üret
QT_QPA_PLATFORM=offscreen .venv/bin/python ... # ekransız test (window.grab() ile ekran görüntüsü)
```

Otomatik test paketi yok. Doğrulama, `QT_QPA_PLATFORM=offscreen` ile uygulamayı açıp `QTimer` ile adımlar çalıştıran ve `window.grab().save(...)` ile ekran görüntüsü alan betiklerle yapıldı.

## Mimari (veri akışı)

```
StreamWorker (QThread, kamera başına)  --frame_ready(cam_id, QImage, stamp)-->  MainWindow
        |  detector.submit(cam_id, frame, stamp)
        v
DetectionEngine (tek QThread) --detections_ready(cam_id, payload)--> MainWindow --> VideoView
WeatherWorker (QThread)       --weather_ready-->
CameraManager: işçileri başlatır/durdurur, odak profilini ayarlar (set_focus).
```

- **Izgara modu:** Akış kare başına 15 fps gösterir ve her 3 karede 1'ini dedektöre gönderir (`FRAME_SKIP`). Dedektör kameraları sırayla işler, takip yapmaz.
- **Odak modu:** Odaktaki akış her kareyi gönderir. Dedektör önce odak kamerasını işler (diğerleri 2 saniyede bir) ve `FocusTracker` (BoT-SORT) çalıştırır.
- **ROI:** Zoom > 1.45 olunca `VideoView.roi_changed`, `DetectionEngine.set_roi` çağırır. Her 8 işten 7'si yalnızca görünen bölgede çalışır. Bu işlerde `partial=True` olur ve sayaçlar son tam kare sonucundan alınır.
- **Kilit:** `VideoView.lock_target` → `DetectionEngine.set_lock`. `TargetLock` sınıfı ViT ile dedektörü birleştirir ve kilitli nesneye sabit `display_id` verir. Kayıpta `payload["lock"]["state"] == "lost"` gelir.
- **Odak görünümünde oynatma:** `VideoView.buffered = True`. Kareler ve tespitler zaman damgalı tamponlarda tutulur. `_advance_playback()` (60 Hz) gecikmeli kareyi seçer, `_interpolate()` kutuları tespitlerin arasında doldurur.
- **Kamera hareketi:** `_tick` içinde yaylı yumuşatma (`_damp`) kullanılır. Kilitliyken nesnenin hızına göre önden gider ve kaybolursa kısa süre tahmini konumu izler.

### Payload biçimi (`detections_ready`)

```python
{"t": monotonic, "ts": frame_stamp, "w": W, "h": H,
 "objects": [{"id": int|None, "cls": coco_id, "category": "person|vehicle|boat|animal",
              "conf": float, "box": (x1, y1, x2, y2)  # 0..1 normalleştirilmiş
             }],
 "counts": {"person":n, "vehicle":n, "boat":n, "animal":n},   # yumuşatılmış
 "partial": bool, "infer_ms": float, "track_ms": float,
 "lock": {"id": int, "state": "detected|tracking|predicted|lost"}  # yalnızca kilitliyken
}
```

## Tasarım kuralları (kullanıcının isteği, bozmayın)

- Neon renk, parlama, "oyun" veya "yapay zekâ üretimi" görünümü yok. Nötr griler, "liquid glass" (bulanık yarı saydam paneller, `painting.paint_glass`) ve ince 1 px kenarlıklar kullanılır.
- Tespit kutuları 1 px, yarı saydam beyaz veya açık gri olur. Kilitli nesnede köşe işaretleri ve ince iz çizgisi bulunur.
- Kamera adları her zaman Türkçe kurallarla BÜYÜK HARF yazılır (`store.tr_upper`, i→İ, ı→I).
- Her ekranın ve diyaloğun altında `Footer` bulunur ("Mete Şahan Tarafından Geliştirilmiştir 2026"). Yeni diyaloglar `widgets.FramedDialog` sınıfından türetilmelidir.
- Varsayılan tema karanlıktır. Tema `settings.json` içindeki `theme` alanından gelir (`preferences.py`), sistem temasını izlemez.
- Arayüz metinleri Türkçedir.
- "Yapay zekâ hazır" ya da cihaz adı gibi teknik durum metinleri arayüzde gösterilmez (kullanıcı kaldırttı).

## Önemli ayrıntılar ve tuzaklar

- Font boyutları `theme.font(px, ...)` ile **piksel** cinsindendir (macOS ve Windows'ta aynı görünsün diye).
- Renkler `theme.current_palette()` üzerinden okunur. QSS, `theme.stylesheet()` ile uygulanır. Özel çizilen widget'lar paleti `paintEvent` içinde okur.
- Video üzerindeki katmanlar her iki temada da koyu camdır (`painting.GLASS_TINT`).
- `cv2.CAP_PROP_N_THREADS=2` ve `cv2.setNumThreads(2)` kullanılır. Gösterilmeyen ve tespite gitmeyen karelerde yalnızca `cap.grab()` çağrılır (CPU tasarrufu).
- `chunklist_w....m3u8` adreslerinin süresi dolabilir. `streaming.candidate_urls` bu durumda `playlist.m3u8` adresini dener.
- **PyInstaller:** torchvision'ın `_C_stable.so` ve `.dylibs` dosyaları spec dosyasına elle eklenir. Eklenmezse paketlenmiş uygulamada `torchvision::nms does not exist` hatası çıkar.
- Paketlenmiş uygulamada `sys.stdout` değeri `None` olabilir. `main.py` bunu `os.devnull` ile karşılar.
- `models/` klasöründe `yolo11s.pt` ve `vittrack.onnx` bulunur. Spec dosyası ikisini de pakete ekler.
- Performans ölçümü (Apple M4, MPS): YOLO11s 1280 px yaklaşık 35–45 ms, BoT-SORT yaklaşık 7–12 ms, ViT yaklaşık 5 ms. Sistem yükü altında belirgin şekilde yavaşlar.

## Bilinen sınırlamalar ve fikirler

- Gece görüntülerinde tekne tespiti zayıf.
- Parçalı (SAHI) tespit, Taksim'de kişi sayısını yaklaşık 2 katına çıkarıyor ama kare başına 178 ms sürüyor. Canlı görüntü için yavaş; isteğe bağlı bir "yüksek hassasiyet" modu olarak eklenebilir.
- Windows paketi hiç test edilmedi.
