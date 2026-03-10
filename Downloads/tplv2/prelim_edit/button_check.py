import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt
from notification_codebase import send_sms, email_coke
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("PyQt Button Example")
        self.setGeometry(100, 100, 400, 300)
        
        # Create a central widget and layout
        
        
        # Create a button
        self.button = QPushButton("Send SMS and Email", self)
        
        # Connect button click to function
        self.button.clicked.connect(lambda : (send_sms(), email_coke()))
        
        # Add button to layout
        
    def button_clicked(self):
        """Function that runs when button is clicked"""
        print("Button was clicked!")
        # Change button text after click
        self.button.setText("Clicked!")

# Run the application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())