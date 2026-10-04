import time
import cv2
import numpy as np

print("cv2:", cv2.__version__, "| optimized:", cv2.useOptimized(), "| threads:", cv2.getNumThreads())
info = cv2.getBuildInformation()
for key in ["IPP", "Parallel framework", "OpenCL", "CUDA", "SIMD", "AVX2", "Baseline"]:
    for line in info.splitlines():
        if line.strip().startswith(key):
            print("  ", line.strip()[:120])

rng = np.random.default_rng(1)
frame = (rng.random((1080, 1920, 3)) * 255).astype(np.uint8)
cv2.rectangle(frame, (400, 400), (600, 500), (255, 255, 255), -1)
tpl = frame[400:464, 600:664].copy()


def bench(name, img, template, n=30):
    cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)  # 预热
    t0 = time.perf_counter()
    for _ in range(n):
        res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    dt = (time.perf_counter() - t0) / n
    ys, xs = np.where(res >= 0.7)
    print(f"  {name}: {dt*1000:.2f} ms/次  命中像素={len(ys)}  图像={img.shape[:2]} 模板={template.shape[:2]}")


print("\n匹配成本分解：")
bench("全帧 1080p + 64x64", frame, tpl)
bench("全帧 1080p + 32x32", frame, cv2.resize(tpl, (32, 32)))
half = cv2.resize(frame, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
bench("降采样 0.5x + 64x64", half, tpl)
half2 = cv2.resize(frame, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
bench("降采样 0.25x + 64x64", half2, tpl)
roi = frame[380:520, 560:700]
bench("ROI 140x140 + 64x64", roi, tpl)

# FFT 互相关（模板较大时可能更快）
print("\nFFT 方案（scipy/numpy，仅作对比）：")
try:
    from numpy.fft import rfft2, irfft2
    f = frame.astype(np.float32).mean(axis=2)
    t = tpl.astype(np.float32).mean(axis=2)
    t0 = time.perf_counter()
    for _ in range(5):
        F = rfft2(f)
        T = rfft2(t, s=f.shape)
        corr = irfft2(F * np.conj(T), s=f.shape)
    dt = (time.perf_counter() - t0) / 5
    print(f"  FFT 全帧灰度: {dt*1000:.2f} ms/次")
except Exception as exc:
    print("  FFT 失败:", exc)
