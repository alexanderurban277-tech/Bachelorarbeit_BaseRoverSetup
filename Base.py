"""

Base_v3 wird keine Daten parsen, sondern nur als Tunnel dienen, der sämtliche eingehenden Daten unverändert weiterleitet.
Das Parsing erfolgt ausschließlich beim Client.

Base_v3 fungiert dabei als SSH-Server, die Authentifizierung erfolgt über Key-Based Authentication.

"""

import asyncio
import asyncssh
import serial_asyncio
import pyrtcm
import base64

BAUDRATE = 460800
SERIAL_DEVICE = '/dev/ttyUSB0'
FILEPATH = '/home/pi/ssh_host_key'

#ssh server "config" class
class MySSHServer(asyncssh.SSHServer):
    def __init__(self,uart_queue,ssh_queue):
        self.uart_queue = uart_queue
        self.ssh_queue = ssh_queue

    def session_requested(self) -> asyncssh.SSHServerSession:
        print("requesting Server session")
        return GNSSServerSession(self.uart_queue, self.ssh_queue)

    def connection_made(self, conn):
        print("Connection received from", conn.get_extra_info('peername'))
        self._conn = conn

    def begin_auth(self, username: str) -> bool:
        try:
            print("Keys set")
            self._conn.set_authorized_keys(f'authorized_keys/{username}')
        
        except Exception as exc:
            print("Error: ", exc)

        return True


#ssh ServerSession protokol
class GNSSServerSession(asyncssh.SSHServerSession):
    def __init__(self,uart_queue,ssh_queue):
        try:
            self.uart_queue = uart_queue
            self.ssh_queue = ssh_queue
            self._input = ''
            self._total = 0
        except Exception as exc:
            print("error initialising the server session: ",exc)

    def connection_made(self, chan):
        self._chan = chan
        print("New SSH session started — sending GNSS stream.")
        task = asyncio.create_task(stream_data(chan,self.uart_queue))
        #task2 = asyncio.create_task(uart_read(self.ssh_queue))

    def shell_requested(self) -> bool:
        return True

    def connection_lost(self, exc):
        print("SSH session closed.")

    def data_received(self, data, datatype):
        self.ssh_queue.put_nowait(data)

#class asyncio serial protocol
class uart_Protocoll(asyncio.Protocol):

    def __init__(self,uart_queue, ssh_queue):
        self.uart_queue  = uart_queue  
        #self.ssh_queue = ssh_queue

    def connection_made(self, transport):
       self.transport = transport
       print(f"Serial port opened")
    
    def data_received(self, data):
        self.uart_queue.put_nowait(data)
    
    def connection_lost(self, exc):
        return super().connection_lost(exc)
  
    def send_command(self, cmd: str):
        if self.transport:
            self.transport.write(cmd.encode('ascii') + b'\r\n')
            if   cmd == "$PAIR002*38\r\n" :
                print("Module Power on")
            elif cmd == "$PAIR003*39\r\n":
                print("Module Power off")
            else:
                print(f"Sent command: {cmd}")

# async def uartl_write -->  gets ssh sent information 
async def uart_write(ssh_queue, protocol):
    while True:
        # Wait until new data is available from the queue
        data = await ssh_queue.get()  # blocks until producer puts something
        print(data)
        # Decode bytes if necessary
        if isinstance(data, bytes):
            line = data.decode('ascii', errors='ignore').strip()
        else:
            line = str(data).strip()

        # Add checksum and send
        cmd = add_checksum(line)
        protocol.send_command(cmd)

#checksum for quectels config messages 
def add_checksum(line):
    line_checksum = line
    checksum = 0
    for i in list(line):
        #print(ord(i))
        checksum = checksum ^ ord(i)  #xor of the ascii bytes
    line_checksum = '$'+ line_checksum + '*'
    line_checksum += format(checksum,'02X')+ '\r' + '\n' #do we need ? --> answer is yes
    return line_checksum
   
#Async ssh data stream
async def stream_data(chan: asyncssh.SSHServerChannel,uart_queue):
    while True:
        data = await uart_queue.get()
        try:
            chan.write(data)
            chan._flush_send_buf()
        except Exception as exc:
            if str(exc) == "Channel not open for sending":
                chan.close()
            else : 
                print("Error during the data Stream: ", exc)

#Opening Server
async def start_server(uart_queue,ssh_queue):
    await asyncssh.create_server(
        server_factory=lambda: MySSHServer(uart_queue,ssh_queue),
        #session_factory=lambda: print("Session factory called") or GNSSServerSession(),
        host='0.0.0.0',
        port=8022,  # SSH server port (not 22 to avoid root)
        server_host_keys=[FILEPATH],encoding = None   # create with ssh-keygen if needed sudo ssh-keygen -t rsa -b 4096 -f /etc/ssh/ssh_host_rsa_key -N ""
    )

#asyasync nc def main --> open serial ports, open ssh tunnel, gather the async functions
async def main():
    
    loop = asyncio.get_event_loop()
    uart_queue = asyncio.Queue() #data from uart 
    ssh_queue = asyncio.Queue()  #data from ssh
    
    #creating server opening port thatslistens for ssh connections 
    await start_server(uart_queue,ssh_queue)

    print("Async SSH GNSS server running on port 8022...")
    #opening serial connection and letting protocoll rule over events/actions
    transport, protocol = await serial_asyncio.create_serial_connection(loop, lambda: uart_Protocoll(uart_queue,ssh_queue), SERIAL_DEVICE,BAUDRATE)

    asyncio.create_task(uart_write(ssh_queue, protocol)) #asyncio.gather(uart_read(ssh_queue,transport),uart_write(ssh_queue, protocol))
    await asyncio.Future()
    #run forever

try:
    asyncio.run(main()) #--> execute programm 
except Exception as exc:
    print("Failed executing main(): ",exc)

