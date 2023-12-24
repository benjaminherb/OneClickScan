import os
import sys
import subprocess
import logging
import numpy as np
from imageio.v3 import imread, imwrite
from PyQt6 import QtWidgets

BASE_DIR = "/home/jonas/Bilder/"
DEVICE_NAME = "genesys:libusb:001:017"
CROP = [0, 0, 0, 0]  # t,b,l,r
SCALE_VALUES = False
ROT90 = 2

# translate to array slices
CROP = [CROP[0], -(CROP[1]+1), CROP[2], -(CROP[3]+1)]


class OneClickScan(QtWidgets.QMainWindow):
    def __init__(self):
        super(OneClickScan, self).__init__()
        self.setMinimumWidth(400)
        self.setWindowTitle("OneClickScan")

        self.dir_name_label = QtWidgets.QLabel("Folder Name:")
        self.dir_name_input = QtWidgets.QLineEdit()

        self.file_name_label = QtWidgets.QLabel("File Name:")
        self.file_name_input = PaddedIntegerSpinbox()

        self.scan_button = QtWidgets.QPushButton("Scan")
        self.scan_button.clicked.connect(self.scan)

        layout = QtWidgets.QGridLayout()
        layout.addWidget(self.dir_name_label, 0, 0)
        layout.addWidget(self.dir_name_input, 0, 1)
        layout.addWidget(self.file_name_label, 1, 0)
        layout.addWidget(self.file_name_input, 1, 1)
        layout.addWidget(self.scan_button, 2, 0, 1, 2)

        main_widget = QtWidgets.QWidget()
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

    def get_output_file(self):
        outdir = os.path.join(BASE_DIR, self.dir_name_input.text())
        outfile = self.file_name_input.text()
        if not os.path.isdir(outdir):
            os.mkdir(outdir)

        if os.path.isfile(outfile):
            self.file_name_input.increment()
            return self.get_output_file()

        return os.path.join(outdir, outfile)

    def scan(self):
        scan_output = "/tmp/tmponeclickscan.tiff"

        self.set_scan_state(True)

        try:
            subprocess.run([
                "scanimage",
                "--device-name", DEVICE_NAME,
                "--format", "tiff",
                "--mode", "Color",
                "--depth", "16",
                "--resolution", "3600",
                "--progress",
                "--output-file", scan_output
            ], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"ScanImageError: {str(e.stderr, 'utf8')}")
            self.set_scan_state(False)
            return False

        img = load_image(scan_output)
        outfile = self.get_output_file()
        imwrite(outfile, (img * 255).astype(np.uint8))
        logging.info(f"Saved image to {outfile}")
        show_image(outfile)
        self.file_name_input.increment()
        self.set_scan_state(False)

        return True

    def set_scan_state(self, scanning):
        if scanning:
            self.scan_button.setDisabled(True)
            self.scan_button.setText("Scanning...")
        else:
            self.scan_button.setDisabled(False)
            self.scan_button.setText("Scan")

        self.scan_button.update()


def linear_to_sRGB(v):
    return ((v > 0.0031308) * (1.055 * np.power(v, (1 / 2.4)) - 0.055)
            + (v <= 0.0031308) * (v * 12.92))


def load_image(path):
    img = imread(path, extension='.tiff')
    img = np.rot90(img, ROT90, axes=(0,1))
    img = img / (2**16 - 1)
    img = linear_to_sRGB(img)
    img = img[CROP[0]:CROP[1], CROP[2]:CROP[3], :]
    if SCALE_VALUES:
        img = (img - img.min()) / (img.max() - img.min())
    return img


def show_image(path):
    # https://stackoverflow.com/a/35305473
    command = {'linux': 'xdg-open', 'win32': 'explorer', 'darwin': 'open'}[sys.platform]
    subprocess.run([command, path])


# Reimplemented to always show padded ints
class PaddedIntegerSpinbox(QtWidgets.QSpinBox):
    def __init__(self, *args):
        super(PaddedIntegerSpinbox, self).__init__(suffix=".jpg")
        self.setRange(0, 9999)

    def textFromValue(self, value):
        return "%06d" % value

    def increment(self):
        self.setValue(self.value() + 1)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("OneClickScan")
    ocs = OneClickScan()
    ocs.show()
    app.exec()
