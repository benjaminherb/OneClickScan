import os
import sys
import subprocess
import tempfile
import logging

from PIL import Image, ImageOps, ImageEnhance
from PyQt6 import QtWidgets, QtGui

BASE_DIR = "/home/ben/Pictures/"
DEVICE_NAME = "genesys:libusb:001:005"


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
            return self.get_output_filename()

        return os.path.join(outdir, outfile)

    def scan(self):
        scan_output = tempfile.mktemp()

        self.set_scan_state(True)

        try:
            subprocess.run([
                "scanimage",
                "--device-name", DEVICE_NAME,
                "--format", "png",
                "--mode", "Color",
                "--resolution", "3600",
                "--progress",
                "--output-file", scan_output
            ], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"ScanImageError: {str(e.stderr, 'utf8')}")
            self.set_scan_state(False)
            return False

        image = Image.open(scan_output)
        img_enhance = ImageEnhance.Brightness(image)
        # image = img_enhance.enhance(3.0)
        image = ImageOps.autocontrast(image, preserve_tone=True)


        outfile = self.get_output_file()
        image.save(outfile)
        logging.info(f"Saved image to {outfile}")
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
