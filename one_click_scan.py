import os
import sys
import re
import subprocess
import logging
import numpy as np
import time
from imageio.v3 import imread, imwrite
from PyQt6 import QtWidgets, QtGui, QtCore

# --- Default Settings --- #
BASE_DIR = "/home/compaq/Bilder/"
DEFAULT_CROP = [0, 350, 0, 280]  # t,b,l,r
DEFAULT_ROTATE = True
SCANNER_ID = '07b3:0c3b'
SCALE_VALUES = True
TEMP_FILE = '.tmpimg.tiff'
DEBUG = True

# --- Setup --- #
if DEBUG:
    BASE_DIR = '/Users/ben/Pictures'
else:
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
        self.dir_name_input = QtWidgets.QComboBox()
        self.dir_name_input.addItems(get_directories(BASE_DIR))
        self.dir_name_input.setEditable(True)
        self.dir_name_input.setCurrentText('')
        self.open_dir_button = QtWidgets.QPushButton('Open')
        self.open_dir_button.clicked.connect(self.open_dir)

        self.dir_name_input.lineEdit().returnPressed.connect(self.scan)

        self.file_name_label = QtWidgets.QLabel("File Name:")
        self.file_name_input = PaddedIntegerSpinbox()
        self.file_name_input.lineEdit().returnPressed.connect(self.scan)

        self.rotate_checkbox = QtWidgets.QCheckBox()
        self.rotate_checkbox.setChecked(DEFAULT_ROTATE)

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
        scan_layout.addWidget(self.dir_name_input, 0, 1)
        scan_layout.addWidget(self.open_dir_button, 0, 2)
        scan_layout.addWidget(self.file_name_label, 1, 0)
        scan_layout.addWidget(self.file_name_input, 1, 1, 1, 2)
        scan_layout.addWidget(self.scan_button, 4, 0, 1, 3)
        scan_layout.setColumnStretch(1, 1)

        settings_layout = QtWidgets.QGridLayout()
        settings_layout.addWidget(QtWidgets.QLabel('Crop (t/b/l/r):'), 0, 0)
        settings_layout.addWidget(self.crop_t_input, 0, 1)
        settings_layout.addWidget(self.crop_b_input, 0, 2)
        settings_layout.addWidget(self.crop_l_input, 0, 3)
        settings_layout.addWidget(self.crop_r_input, 0, 4)
        settings_layout.addWidget(QtWidgets.QLabel('Rotate (180°):'), 1, 0)
        settings_layout.addWidget(self.rotate_checkbox, 1, 1, 1, 4)

        scan_widget = QtWidgets.QWidget()
        scan_widget.setLayout(scan_layout)
        settings_widget = QtWidgets.QWidget()
        settings_widget.setLayout(settings_layout)
        tab_widget = QtWidgets.QTabWidget()
        tab_widget.addTab(scan_widget, 'Scanning')
        tab_widget.addTab(settings_widget, 'Settings')
        self.setCentralWidget(tab_widget)

    def get_output_file(self):
        outdir = os.path.join(BASE_DIR, self.dir_name_input.currentText())
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

        scan_output = TEMP_FILE
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
                time.sleep(0.5)
                self.refresh()

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

        self.refresh()

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

    def open_dir(self):
        d = os.path.join(BASE_DIR, self.dir_name_input.currentText())
        if not os.path.exists(d):
            d = BASE_DIR
        command = {'linux': 'xdg-open', 'win32': 'explorer', 'darwin': 'open'}[sys.platform]
        subprocess.Popen([command, d])


    def refresh(self):
        self.app.processEvents()
        current_directory = self.dir_name_input.currentText()
        self.dir_name_input.clear()
        self.dir_name_input.addItems(get_directories(BASE_DIR))
        self.dir_name_input.setCurrentText(current_directory)


def get_directories(path):
    return [d for d in os.listdir(path) if os.path.isdir(d) and not d.startswith('.')]


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
