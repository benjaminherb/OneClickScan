import os
import sys
import re
import subprocess
import logging
import numpy as np
import time
from imageio.v3 import imread, imwrite
from PyQt6 import QtWidgets, QtGui, QtCore

BASE_DIR = "/home/compaq/Bilder/"
SCANNER_ID = '07b3:0c3b'
DEFAULT_CROP = [0, 350, 0, 280]  # t,b,l,r
SCALE_VALUES = True

lsusb = subprocess.run(["lsusb", "-d", SCANNER_ID], check=True, stdout=subprocess.PIPE, text=True).stdout
match = re.match("Bus (\d{3}) Device (\d{3}): *", lsusb)
if match is None:
    logging.error("Scanner not found, please plug it in NOW!")
    exit()

DEVICE_NAME = f"genesys:libusb:{match[1]}:{match[2]}"


class OneClickScan(QtWidgets.QMainWindow):
    def __init__(self, app=None):
        super(OneClickScan, self).__init__()
        self.app = app
        self.setMinimumWidth(400)
        self.setWindowTitle("OneClickScan")

        self.dir_name_label = QtWidgets.QLabel("Folder Name:")
        self.dir_name_input = QtWidgets.QLineEdit()
        self.dir_name_input.returnPressed.connect(self.scan)

        self.file_name_label = QtWidgets.QLabel("File Name:")
        self.file_name_input = PaddedIntegerSpinbox()
        self.file_name_input.lineEdit().returnPressed.connect(self.scan)

        self.rotate_checkbox = QtWidgets.QCheckBox()
        self.rotate_checkbox.setChecked(True)

        self.crop_t_input = QtWidgets.QSpinBox()
        self.crop_b_input = QtWidgets.QSpinBox()
        self.crop_l_input = QtWidgets.QSpinBox()
        self.crop_r_input = QtWidgets.QSpinBox()
        for i, sb in enumerate([self.crop_t_input, self.crop_b_input, self.crop_l_input, self.crop_r_input]):
            sb.setMinimum(0)
            sb.setMaximum(2000)
            sb.setValue(DEFAULT_CROP[i])

        self.scan_button = QtWidgets.QPushButton("Scan")
        self.scan_button.clicked.connect(self.scan)

        scan_layout = QtWidgets.QGridLayout()
        scan_layout.addWidget(self.dir_name_label, 0, 0)
        scan_layout.addWidget(self.dir_name_input, 0, 1, 1, 4)
        scan_layout.addWidget(self.file_name_label, 1, 0)
        scan_layout.addWidget(self.file_name_input, 1, 1, 1, 4)
        scan_layout.addWidget(self.scan_button, 4, 0, 1, 5)

        settings_layout = QtWidgets.QGridLayout()
        settings_layout.addWidget(QtWidgets.QLabel('Crop (t/b/l/r):'), 2, 0)
        settings_layout.addWidget(self.crop_t_input, 2, 1)
        settings_layout.addWidget(self.crop_b_input, 2, 2)
        settings_layout.addWidget(self.crop_l_input, 2, 3)
        settings_layout.addWidget(self.crop_r_input, 2, 4)
        settings_layout.addWidget(QtWidgets.QLabel('Rotate (180°):'), 3, 0)
        settings_layout.addWidget(self.rotate_checkbox, 3, 1, 1, 4)

        scan_widget = QtWidgets.QWidget()
        scan_widget.setLayout(scan_layout)
        settings_widget = QtWidgets.QWidget()
        settings_widget.setLayout(settings_layout)
        tab_widget = QtWidgets.QTabWidget()
        tab_widget.addTab(scan_widget, 'Scanning')
        tab_widget.addTab(settings_widget, 'Settings')
        self.setCentralWidget(tab_widget)

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
        outfile = self.get_output_file()
        if os.path.isfile(outfile):
            answer = QtWidgets.QMessageBox.question(
                self, '', f"The {outfile} already exists! Overwrite?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
            if answer == QtWidgets.QMessageBox.StandardButton.No:
                return False

        self.set_scan_state(True)

        scan_output = "/tmp/tmponeclickscan.tiff"
        try:
            process = subprocess.Popen([
                "scanimage",
                "--device-name", DEVICE_NAME,
                "--format", "tiff",
                "--mode", "Color",
                "--depth", "16",
                "--resolution", "3600",
                "--progress",
                "--output-file", scan_output
            ])
            while process.poll() is None:
                time.sleep(0.2)
                self.app.processEvents()

        except subprocess.CalledProcessError as e:
            logging.error(f"ScanImageError: {str(e.stderr, 'utf8')}")
            self.set_scan_state(False)
            return False

        img = self.load_image(scan_output)
        imwrite(outfile, (img * 255).astype(np.uint8))
        logging.info(f"Saved image to {outfile}")
        show_image(outfile)
        self.file_name_input.increment()
        self.set_scan_state(False)

        return True

    def set_scan_state(self, scanning):
        self.scan_button.setDisabled(scanning)
        self.file_name_input.setDisabled(scanning)
        self.dir_name_input.setDisabled(scanning)
        self.rotate_checkbox.setDisabled(scanning)
        self.crop_t_input.setDisabled(scanning)
        self.crop_b_input.setDisabled(scanning)
        self.crop_l_input.setDisabled(scanning)
        self.crop_r_input.setDisabled(scanning)

        self.scan_button.setText("Scan")
        if scanning:
            self.scan_button.setText("Scanning...")

        self.app.processEvents()

    def keyPressEvent(self, event):
        if type(event) == QtGui.QKeyEvent:
            if event.key() == QtCore.Qt.Key.Key_Enter:
                self.scan()

    def load_image(self, path):
        img = imread(path, extension='.tiff')
        if self.rotate_checkbox.isChecked():
            img = np.rot90(img, 2, axes=(0, 1))
        crop = self.get_crop()
        img = img[crop[0]:crop[1], crop[2]:crop[3], :]
        img = img / (2**16 - 1)
        img = linear_to_sRGB(img)
        if SCALE_VALUES:
            img = (img - img.min()) / (img.max() - img.min())
        return img

    def get_crop(self):
        return [
            self.crop_t_input.value(), -(self.crop_b_input.value()+1),
            self.crop_l_input.value(), -(self.crop_r_input.value()+1)
        ]


def linear_to_sRGB(v):
    return ((v > 0.0031308) * (1.055 * np.power(v, (1 / 2.4)) - 0.055)
            + (v <= 0.0031308) * (v * 12.92))


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
    ocs = OneClickScan(app)
    ocs.show()
    app.exec()
