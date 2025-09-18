import sys
import types

import numpy as np

cv2_stub = types.ModuleType("cv2")

# Constants
cv2_stub.COLOR_BGR2GRAY = 6
cv2_stub.THRESH_BINARY_INV = 1
cv2_stub.THRESH_OTSU = 8
cv2_stub.THRESH_BINARY = 0
cv2_stub.ADAPTIVE_THRESH_GAUSSIAN_C = 0
cv2_stub.MORPH_RECT = 0
cv2_stub.MORPH_CLOSE = 3
cv2_stub.MORPH_OPEN = 2
cv2_stub.RETR_EXTERNAL = 0
cv2_stub.CHAIN_APPROX_SIMPLE = 2
cv2_stub.LINE_AA = 16
cv2_stub.FONT_HERSHEY_SIMPLEX = 0


def _ensure_gray(image):
    if image.ndim == 2:
        return image
    return image.mean(axis=2).astype(np.uint8)


def cvtColor(image, flag):
    return _ensure_gray(image)


cv2_stub.cvtColor = cvtColor


def _convolve(image, kernel):
    kh, kw = kernel.shape
    pad_h = kh // 2
    pad_w = kw // 2
    padded = np.pad(image, ((pad_h, pad_h), (pad_w, pad_w)), mode="reflect")
    out = np.zeros_like(image, dtype=float)
    for y in range(image.shape[0]):
        for x in range(image.shape[1]):
            region = padded[y:y + kh, x:x + kw]
            out[y, x] = np.sum(region * kernel)
    return out


def GaussianBlur(image, ksize, sigma):
    ky, kx = ksize
    kernel = np.ones((ky, kx), dtype=float)
    kernel /= kernel.sum()
    blurred = _convolve(image.astype(float), kernel)
    return blurred.astype(np.uint8)


cv2_stub.GaussianBlur = GaussianBlur


def medianBlur(image, ksize):
    kh = kw = ksize
    pad_h = kh // 2
    pad_w = kw // 2
    padded = np.pad(image, ((pad_h, pad_h), (pad_w, pad_w)), mode="edge")
    out = np.zeros_like(image)
    for y in range(image.shape[0]):
        for x in range(image.shape[1]):
            region = padded[y:y + kh, x:x + kw]
            out[y, x] = np.median(region)
    return out


cv2_stub.medianBlur = medianBlur


def threshold(src, thresh, maxval, ttype):
    if ttype & cv2_stub.THRESH_OTSU:
        thresh = 128
    if ttype & cv2_stub.THRESH_BINARY_INV:
        dst = np.where(src <= thresh, maxval, 0).astype(np.uint8)
    else:
        dst = np.where(src > thresh, maxval, 0).astype(np.uint8)
    return thresh, dst


cv2_stub.threshold = threshold


def adaptiveThreshold(src, maxval, method, ttype, blockSize, C):
    pad = blockSize // 2
    padded = np.pad(src, pad, mode="reflect")
    out = np.zeros_like(src)
    for y in range(src.shape[0]):
        for x in range(src.shape[1]):
            block = padded[y:y + blockSize, x:x + blockSize]
            thresh = block.mean() - C
            if ttype == cv2_stub.THRESH_BINARY_INV:
                out[y, x] = maxval if src[y, x] < thresh else 0
            else:
                out[y, x] = maxval if src[y, x] > thresh else 0
    return out


cv2_stub.adaptiveThreshold = adaptiveThreshold


def bitwise_or(a, b):
    return np.maximum(a, b).astype(np.uint8)


cv2_stub.bitwise_or = bitwise_or


def getStructuringElement(shape, ksize):
    kw, kh = ksize
    return np.ones((kh, kw), dtype=np.uint8)


cv2_stub.getStructuringElement = getStructuringElement


def _erode(image, kernel):
    kh, kw = kernel.shape
    pad_h = kh // 2
    pad_w = kw // 2
    padded = np.pad(image, ((pad_h, pad_h), (pad_w, pad_w)), mode="constant")
    out = np.zeros_like(image)
    for y in range(image.shape[0]):
        for x in range(image.shape[1]):
            region = padded[y:y + kh, x:x + kw]
            if np.all(region[kernel > 0] > 0):
                out[y, x] = 255
    return out


def _dilate(image, kernel):
    kh, kw = kernel.shape
    pad_h = kh // 2
    pad_w = kw // 2
    padded = np.pad(image, ((pad_h, pad_h), (pad_w, pad_w)), mode="constant")
    out = np.zeros_like(image)
    for y in range(image.shape[0]):
        for x in range(image.shape[1]):
            region = padded[y:y + kh, x:x + kw]
            if np.any(region[kernel > 0] > 0):
                out[y, x] = 255
    return out


def _open_horizontal(image, length):
    binary = (image > 0).astype(np.uint8)
    h, w = binary.shape
    out = np.zeros_like(binary, dtype=np.uint8)
    for y in range(h):
        run = 0
        for x in range(w):
            if binary[y, x]:
                run += 1
            else:
                if run >= length:
                    out[y, x - run:x] = 255
                run = 0
        if run >= length:
            out[y, w - run:w] = 255
    return out


def _open_vertical(image, length):
    binary = (image > 0).astype(np.uint8)
    h, w = binary.shape
    out = np.zeros_like(binary, dtype=np.uint8)
    threshold = max(length, 10)
    for x in range(w):
        run = 0
        for y in range(h):
            if binary[y, x]:
                run += 1
            else:
                if run >= threshold:
                    out[y - run:y, x] = 255
                run = 0
        if run >= threshold:
            out[h - run:h, x] = 255
    return out


def morphologyEx(image, op, kernel, iterations=1):
    result = image.copy()
    for _ in range(iterations):
        if op == cv2_stub.MORPH_CLOSE:
            result = _erode(_dilate(result, kernel), kernel)
        elif op == cv2_stub.MORPH_OPEN:
            kh, kw = kernel.shape
            if kh == 1 and kw > 1:
                result = _open_horizontal(result, kw)
            elif kw == 1 and kh > 1:
                result = _open_vertical(result, kh)
            else:
                result = _dilate(_erode(result, kernel), kernel)
    return result


cv2_stub.morphologyEx = morphologyEx


def dilate(image, kernel, iterations=1):
    result = image.copy()
    for _ in range(iterations):
        result = _dilate(result, kernel)
    return result


cv2_stub.dilate = dilate


def countNonZero(image):
    return int(np.count_nonzero(image))


cv2_stub.countNonZero = countNonZero


def _component_pixels(binary):
    visited = np.zeros_like(binary, dtype=bool)
    contours = []
    height, width = binary.shape
    for y in range(height):
        for x in range(width):
            if binary[y, x] == 0 or visited[y, x]:
                continue
            stack = [(y, x)]
            pixels = []
            visited[y, x] = True
            while stack:
                cy, cx = stack.pop()
                pixels.append((cx, cy))
                for ny in range(cy - 1, cy + 2):
                    for nx in range(cx - 1, cx + 2):
                        if 0 <= ny < height and 0 <= nx < width:
                            if binary[ny, nx] > 0 and not visited[ny, nx]:
                                visited[ny, nx] = True
                                stack.append((ny, nx))
            contours.append(pixels)
    return contours


def findContours(image, mode, method):
    binary = (image > 0).astype(np.uint8)
    components = _component_pixels(binary)
    contours = []
    for pixels in components:
        if not pixels:
            continue
        pts = np.array([[x, y] for x, y in pixels], dtype=np.int32)
        contours.append(pts.reshape(-1, 1, 2))
    return contours, None


cv2_stub.findContours = findContours


def boundingRect(contour):
    pts = contour.reshape(-1, 2)
    min_x = int(pts[:, 0].min())
    min_y = int(pts[:, 1].min())
    max_x = int(pts[:, 0].max())
    max_y = int(pts[:, 1].max())
    return min_x, min_y, max_x - min_x + 1, max_y - min_y + 1


cv2_stub.boundingRect = boundingRect


def contourArea(contour):
    pts = contour.reshape(-1, 2)
    min_x, min_y = pts[:, 0].min(), pts[:, 1].min()
    max_x, max_y = pts[:, 0].max(), pts[:, 1].max()
    return float((max_x - min_x + 1) * (max_y - min_y + 1))


cv2_stub.contourArea = contourArea


def arcLength(contour, closed):
    x, y, w, h = boundingRect(contour)
    return float(2 * (w + h))


cv2_stub.arcLength = arcLength


def approxPolyDP(contour, epsilon, closed):
    x, y, w, h = boundingRect(contour)
    return np.array([[[x, y]], [[x + w, y]], [[x + w, y + h]], [[x, y + h]]], dtype=np.int32)


cv2_stub.approxPolyDP = approxPolyDP


def Canny(image, t1, t2):
    image = image.astype(float)
    sobel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]])
    sobel_y = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]])
    gx = _convolve(image, sobel_x)
    gy = _convolve(image, sobel_y)
    mag = np.sqrt(gx ** 2 + gy ** 2)
    return (mag > t1).astype(np.uint8) * 255


cv2_stub.Canny = Canny


def rectangle(image, pt1, pt2, color, thickness):
    x0, y0 = pt1
    x1, y1 = pt2
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    if thickness < 0:
        image[y0:y1 + 1, x0:x1 + 1] = color
        return image
    image[y0:y0 + thickness, x0:x1 + 1] = color
    image[y1 - thickness + 1:y1 + 1, x0:x1 + 1] = color
    image[y0:y1 + 1, x0:x0 + thickness] = color
    image[y0:y1 + 1, x1 - thickness + 1:x1 + 1] = color
    return image


cv2_stub.rectangle = rectangle


def putText(image, text, org, font, font_scale, color, thickness, line_type):
    # No-op for stub
    return image


cv2_stub.putText = putText


sys.modules.setdefault("cv2", cv2_stub)
