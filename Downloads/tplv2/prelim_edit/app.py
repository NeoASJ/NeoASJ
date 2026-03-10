import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QComboBox, QScrollArea, QGridLayout, QDialog
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

ROOT_DIR = "detections"   # change if needed
IMG_EXT = (".jpg", ".jpeg", ".png")

# =====================================================
# Full Image Viewer (Maximized)
# =====================================================
class FullImageViewer(QDialog):
    def __init__(self, image_path):
        super().__init__()
        self.setWindowTitle(os.path.basename(image_path))
        self.showMaximized()

        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)

        pixmap = QPixmap(image_path)
        label.setPixmap(pixmap)

        scroll.setWidget(label)
        layout.addWidget(scroll)


# =====================================================
# Clickable Image Label
# =====================================================
class ClickableLabel(QLabel):
    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path

    def mousePressEvent(self, event):
        viewer = FullImageViewer(self.image_path)
        viewer.exec_()


# =====================================================
# Main Application
# =====================================================
class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image History Viewer")
        self.resize(1200, 800)

        main_layout = QVBoxLayout(self)

        # ---------------- Controls ----------------
        control_layout = QHBoxLayout()

        self.folder_combo = QComboBox()
        self.date_combo = QComboBox()

        self.folder_combo.currentTextChanged.connect(self.load_dates)
        self.date_combo.currentTextChanged.connect(self.load_images)

        control_layout.addWidget(QLabel("Folder:"))
        control_layout.addWidget(self.folder_combo)
        control_layout.addWidget(QLabel("Date:"))
        control_layout.addWidget(self.date_combo)

        main_layout.addLayout(control_layout)

        # ---------------- Scroll Area ----------------
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.scroll_widget = QWidget()
        self.grid = QGridLayout(self.scroll_widget)
        self.grid.setSpacing(15)

        self.scroll.setWidget(self.scroll_widget)
        main_layout.addWidget(self.scroll)

        self.load_folders()

    # ---------------- Loaders ----------------
    def load_folders(self):
        self.folder_combo.clear()
        if not os.path.exists(ROOT_DIR):
            return

        folders = sorted(
            f for f in os.listdir(ROOT_DIR)
            if os.path.isdir(os.path.join(ROOT_DIR, f))
        )
        self.folder_combo.addItems(folders)

    def load_dates(self, folder):
        self.date_combo.clear()
        folder_path = os.path.join(ROOT_DIR, folder)

        if not os.path.exists(folder_path):
            return

        date_dirs = []
        for d in os.listdir(folder_path):
            if os.path.isdir(os.path.join(folder_path, d)):
                date_dirs.append(d)

        dates = sorted(date_dirs, reverse=True)
        self.date_combo.addItems(dates)


    def load_images(self, date):
        self.clear_grid()

        folder = self.folder_combo.currentText()
        img_dir = os.path.join(ROOT_DIR, folder, date)
        if not os.path.exists(img_dir):
            return

        images = sorted(
            f for f in os.listdir(img_dir)
            if f.lower().endswith(IMG_EXT)
        )

        row = col = 0
        for img in images:
            image_path = os.path.join(img_dir, img)
            cell = self.create_image_cell(image_path)

            self.grid.addWidget(cell, row, col)

            col += 1
            if col >= 3:
                col = 0
                row += 1

    # ---------------- UI helpers ----------------
    def create_image_cell(self, image_path):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignCenter)

        # Thumbnail
        thumb = ClickableLabel(image_path)
        thumb.setAlignment(Qt.AlignCenter)

        pixmap = QPixmap(image_path)
        pixmap = pixmap.scaled(
            300, 220,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        thumb.setPixmap(pixmap)

        # Filename
        name_label = QLabel(os.path.basename(image_path))
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setStyleSheet("font-size: 10px;")

        layout.addWidget(thumb)
        layout.addWidget(name_label)

        return container

    def clear_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()


# =====================================================
# Entry Point
# =====================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec_())