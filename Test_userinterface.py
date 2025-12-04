
import sys
import threading
import time
from PyQt5 import QtWidgets, QtCore, QtGui
from queue import Queue
import asyncio
import asyncssh
import base64
import pyrtcm


#FILEPATH of private key
FILEPATH = "location of your clients private key" # must be modified
#Device Username 
USERNAME = "clients username" #must be modified
#Port
PORT = 8022
#UI Update Rate
UPDATE = 0.05

nmea_data_queue = Queue() #strores nmea data
rtcm_data_queue = Queue() #stores rtcm data
confg_data_queue = Queue() #stores confg data
ssh_cmd_queue_1 = Queue() #command queue for Base
ssh_cmd_queue_2 = Queue() #command queue for Rover

class Client_Session(asyncssh.SSHClientSession):
    def __init__(self,rtcm_data_queue, nmea_data_queue, confg_data_queue):
        print("Session init")
        self.buffer = b''
        self.rtcm_buffer = b''
        self.rtcm_queue = rtcm_data_queue
        self.confg_queue = confg_data_queue
        self.nmea_queue = nmea_data_queue

    def connection_made(self, chan):
        self._chan = chan
        print("SSH session established")
        #task = asyncio.create_task(read_console(chan))   # commented out becaude read_console needs to be updated   

    def data_received(self,data, datatype: asyncssh.DataType):
        self.buffer += data
        #extra rtcm buffer 
        self.rtcm_buffer += data 
        
        # rtcm bit structure: 8 bits Preamble, 6 bits reserved, 10 bits Message length 
        #0-1023 Bytes of data, 24 Bits CRC
        if self.rtcm_buffer[0] == 0xD3: 
            if len(self.rtcm_buffer) >= 3:  # ensure we have at least preamble+length bytes
    # Extract 10-bit payload length (ignoring 6 reserved bits)
                payload_length = ((self.rtcm_buffer[1] & 0x03) << 8) | self.rtcm_buffer[2]
    # Calculate total message length including CRC
                total_length = 1 + 2 + payload_length + 3
                if len(self.rtcm_buffer) >= total_length:
                    try: 
                      #reine message 
                      message = self.rtcm_buffer[:total_length] 
        #rest was gröser ist packen wir zurück in buffer da es wichtige nachrichten enthalen könnte 
                      self.rtcm_buffer  = self.rtcm_buffer[total_length:] 
                      if not pyrtcm.rtcmhelpers.calc_crc24q(message):     #funktion liefert 0 wenn CRC korrekt ist --> korrekte RTCM daten                     
                          payload = message[:-3]  # Header + CRC ausgeschlossen
                          self.rtcm_queue.put(payload)
                          print(payload.hex())
                          #self.uart_queue.put_nowait(payload)
                    except Exception:
                          pass
        else :
            self.rtcm_buffer = self.rtcm_buffer = self.rtcm_buffer[1:]


        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            line = line.rsplit(b'$', 1)[-1]  # get the part after last '$', '$' wird weg gekürzt!!
            line = line.strip() #wir machen dass weil wir alles in den buffer hauen und die ascii messages nur mit dem \n
                                # erkennen, dachtung eventuel rtcm nachrichten teile in der message 
                                #deshalb nochmal bei dem "$" differenzieren --> nicht unmöglich dass hier 
                                #rtcm messages mitkommen wenn diese unglüch die zeichen im payload haben

            if line.startswith(b'P'): #amrk the config messages, only want to see these ones, '$' beginning to distinguish from nmea data
                line = '$' + line.decode('ascii', errors='ignore')
                self.confg_queue.put(line)
                # Put decoded line into asyncio queue
            else:
                #print(line.decode('ascii', errors='ignore'))
                if line.startswith(b'G'):
                    self.nmea_queue.put(line.decode('ascii', errors='ignore'))
                else :
                    pass
      
    

    def connection_lost(self, exc):
        print("SSH session closed", exc)


class Client(asyncssh.SSHClient):
    def connection_made(self, conn: asyncssh.SSHClientConnection) -> None:
        print(f'Connection made to {conn.get_extra_info('peername')[0]}.')

    def auth_completed(self) -> None:
        print('Authentication successful.')

async def send_cmd_ssh(channel_1: asyncssh.SSHClientChannel, ssh_cmd_queue_1):
    while True:
            try: 
                data_1 = await asyncio.to_thread(ssh_cmd_queue_1.get)
                print(data_1)
                channel_1.write(data_1.encode('ascii'))
                #channel_1._flush_send_buf()
                #await channel_1.drain()
            except (asyncssh.Error, OSError) as exc:
                print('SSH connection failed:', exc)

async def ssh_BaseConnect_main(rtcm_data_queue, nmea_data_queue, confg_data_queue):
    try:
       conn, client = await asyncssh.create_connection(Client, 'raspberrypi.local', port= PORT,username= USERNAME,known_hosts=None, client_keys=[FILEPATH])
       async with conn:     
        # Open a session channel
            chan, session = await conn.create_session(lambda: Client_Session(rtcm_data_queue, nmea_data_queue, confg_data_queue),command=None,encoding = None)
            task = asyncio.create_task(send_cmd_ssh(chan,ssh_cmd_queue_1))
            #print("Connected to GNSS server, receiving stream...")
            await chan.wait_closed()


    except (asyncssh.Error, OSError) as exc:
        print('SSH connection failed:', exc)

def start_async_loop(rtcm_data_queue, nmea_data_queue, confg_data_queue):
    asyncio.run(ssh_BaseConnect_main(rtcm_data_queue, nmea_data_queue, confg_data_queue))

def read_data_file(queue):
    """Simulate reading data from a file updated via SSH."""
    data = queue.get()
    try:
        if isinstance(data,str):
            return data
        elif isinstance(data,bytes):
            return data.hex()
    except Exception as e:
        return f"Error: {e}"

def send_to_relay(data_list):
    ssh_cmd_queue_1.put(data_list[0])

# ------------------------
# Data Window Class
# ------------------------
class DataWindow(QtWidgets.QWidget):
    def __init__(self, title, data_queue):
        super().__init__()
        self.queue = data_queue
        self.setWindowTitle(title)
        self.layout = QtWidgets.QVBoxLayout()
        self.text_display = QtWidgets.QTextEdit()
        self.text_display.setReadOnly(True)
        self.layout.addWidget(self.text_display)
        self.setLayout(self.layout)
        # Start update thread
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

    def update_loop(self):
        while True:
            data = read_data_file(self.queue)  # or get from queue
            # Append new data instead of overwriting
            QtCore.QMetaObject.invokeMethod(
            self.text_display, "append",  # use "append" instead of setPlainText
            QtCore.Qt.QueuedConnection, 
            QtCore.Q_ARG(str, data)
            )
            time.sleep(UPDATE)  # update every 0.05 seconds

# ------------------------
# Main Window with Menu
# ------------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, rtcm_data_queue, nmea_data_queue, confg_data_queue):
        self.rtcm_queue = rtcm_data_queue
        self.confg_queue = confg_data_queue
        self.nmea_queue = nmea_data_queue
        super().__init__()
        self.setWindowTitle("Data Analysis UI")
        self.setGeometry(100, 100, 500, 300)

        # Buttons to open data windows
        self.button_layout = QtWidgets.QVBoxLayout()
        self.btn_window1 = QtWidgets.QPushButton("Open NMEA Datastream Window")
        self.btn_window1.clicked.connect(lambda: self.open_data_window("Datastream", self.nmea_queue))
        self.btn_window2 = QtWidgets.QPushButton("Open Config Data Window")
        self.btn_window2.clicked.connect(lambda: self.open_data_window("Config Base (excluding '$' and checksum)", self.confg_queue))
        self.button_layout.addWidget(self.btn_window1)
        self.button_layout.addWidget(self.btn_window2)
        self.btn_window3 = QtWidgets.QPushButton("Open rtcm Datastream Window")
        self.btn_window3.clicked.connect(lambda: self.open_data_window("Datastream", self.rtcm_queue))
        self.button_layout.addWidget(self.btn_window3)

        # Four input fields
        # Four input fields with labels
        titles = [
    "Config Message (excluding checksum)",
    "Correction frequency (Hz)",
    "Wrong data",
    "Title 4"  # You can change this to the proper label
]

        self.inputs = []
        for i, title in enumerate(titles):
            label = QtWidgets.QLabel(title)
            line_edit = QtWidgets.QLineEdit()
            line_edit.setPlaceholderText(f"Enter {title}")
            self.button_layout.addWidget(label)
            self.button_layout.addWidget(line_edit)
            self.inputs.append(line_edit)


        # Big Relay Button
        self.relay_button = QtWidgets.QPushButton("Send Data")
        self.relay_button.setMinimumHeight(50)  # make it bigger
        self.relay_button.setFont(QtGui.QFont("Arial", 14, QtGui.QFont.Bold))
        self.relay_button.clicked.connect(self.send_all_data)
        self.button_layout.addWidget(self.relay_button)

        container = QtWidgets.QWidget()
        container.setLayout(self.button_layout)
        self.setCentralWidget(container)

        self.data_windows = []

    def open_data_window(self, title, data_queue):
        win = DataWindow(title, data_queue)
        self.data_windows.append(win)  # Keep a reference
        win.show()

    def send_all_data(self):
        data_list = [field.text() for field in self.inputs]
        send_to_relay(data_list)

# ------------------------
# Run App
# ------------------------
if __name__ == "__main__":
    #Background Thread
    threading.Thread(target=lambda: start_async_loop(rtcm_data_queue, nmea_data_queue, confg_data_queue),daemon=True).start()
    
    # Start the UI
    app = QtWidgets.QApplication(sys.argv)
    main_win = MainWindow(rtcm_data_queue, nmea_data_queue, confg_data_queue)
    main_win.show()
    sys.exit(app.exec_())

