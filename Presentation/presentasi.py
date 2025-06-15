import torch
import cv2
import cvzone
from torchvision import transforms
import time
import serial

try:
    arduino = serial.Serial(port='COM3', baudrate=115200, timeout=1)
    time.sleep(2)
    print("Koneksi ke Arduino berhasil!")
except Exception as e:
    print(f"Gagal konek ke Arduino: {e}")
    exit()

device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')

from torchvision.models.detection import ssdlite320_mobilenet_v3_large, SSDLite320_MobileNet_V3_Large_Weights
weights = SSDLite320_MobileNet_V3_Large_Weights.DEFAULT
model = ssdlite320_mobilenet_v3_large(weights=weights)
model.to(device)
model.eval()

with open('classes.txt', 'r') as f:
    classnames = f.read().splitlines()
print(f"Jumlah kelas: {len(classnames)}")

def is_valid_class(class_id):
    return 0 < class_id <= len(classnames) and classnames[class_id - 1] != 'N/A'

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Error: Tidak dapat membuka webcam.")
    exit()

transform = transforms.ToTensor()
confidence_threshold = 0.6
last_command = None

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: Tidak dapat membaca frame dari webcam.")
        break

    frame = cv2.resize(frame, (1200, 1000))
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img_tensor = transform(img_rgb).to(device)

    with torch.no_grad():
        pred = model([img_tensor])[0]

    boxes = pred['boxes']
    scores = pred['scores']
    labels = pred['labels']

    command = '0'

    for i in range(len(scores)):
        score = scores[i].item()
        class_id = labels[i].item()

        if score > confidence_threshold and is_valid_class(class_id):
            class_name = classnames[class_id - 1]
            x1, y1, x2, y2 = boxes[i].cpu().numpy().astype(int)
            bbox_height = y2 - y1

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{class_name}: {score:.2f}"
            cvzone.putTextRect(frame, label, [x1, y1 - 10], scale=1.5, thickness=2, offset=5, border=2)

            if class_name == '__background__':
                command = '0'
            elif bbox_height > 800:
                print(f"Objek terlalu dekat (<1m), tinggi bbox: {bbox_height}px")
                command = '4'
            else:
                print(f"Deteksi: {class_name} ({score:.2f}), tinggi bbox: {bbox_height}px")
                command = '1'
            break

    print(f"Command sekarang: {command}, Last command: {last_command}")

    if command != last_command:
        arduino.write(command.encode())
        print(f"Kirim ke Arduino: {command}")
        last_command = command

    cv2.imshow("SSDLite Realtime Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()