import time
import cv2
import numpy as np

rng = np.random.default_rng(1)
frame = (rng.random((1080, 1920, 3)) * 255).astype(np.uint8)
cv2.rectangle(frame, (400, 400), (600, 500), (255, 255, 255), -1)
tpl = frame[400:464, 600:664].copy()

print("OpenCL 可用:", cv2.ocl.haveOpenCL())
if cv2.ocl.haveOpenCL():
    cv2.ocl.setUseOpenCL(True)
    print("使用中:", cv2.ocl.useOpenCL())


def bench(name, img, template, n=20, use_umat=False):
    def run():
        if use_umat:
            u_img = cv2.UMat(img)
            u_tpl = cv2.UMat(template)
            r = cv2.matchTemplate(u_img, u_tpl, cv2.TM_CCOEFF_NORMED)
            return r.get()
        return cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)

    run()
    t0 = time.perf_counter()
    for _ in range(n):
        res = run()
    dt = (time.perf_counter() - t0) / n
    ys, xs = np.where(res >= 0.7)
    print(f"  {name}: {dt*1000:.2f} ms/次 命中={len(ys)}")


print("\nCPU vs OpenCL（全帧 1080p，64x64 模板）:")
bench("CPU ", frame, tpl)
bench("OpenCL", frame, tpl, use_umat=True)

print("\nCPU vs OpenCL（ROI 400x300）:")
roi = frame[380:680, 560:960]
bench("CPU ", roi, tpl)
bench("OpenCL", roi, tpl, use_umat=True)
