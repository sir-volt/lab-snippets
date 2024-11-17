from snippets.lab2 import *
import threading


# Uncomment this line to observe timeout errors more often.
# Beware: short timeouts can make demonstrations more difficult to follow.
# socket.setdefaulttimeout(5) # set default timeout for blocking operations to 5 seconds


class Connection:
    def __init__(self, socket: socket.socket, callback=None):
        self.__socket = socket
        self.local_address = self.__socket.getsockname()
        self.remote_address = self.__socket.getpeername()
        self.__notify_closed = False
        self.__callback = callback
        self.__receiver_thread = threading.Thread(target=self.__handle_incoming_messages, daemon=True)
        if self.__callback:
            self.__receiver_thread.start()

    # decoratore che ritorna la callback
    @property
    def callback(self):
        return self.__callback or (lambda *_: None)
    
    # decoratore che setta la callback per la Connection
    @callback.setter
    def callback(self, value):
        if self.__callback:
            raise ValueError("Callback can only be set once")
        self.__callback = value
        if value:
            self.__receiver_thread.start()

    @property
    def closed(self):
        return self.__socket._closed
    
    # questa funzione serve per inviare i messaggi, lo codifica in bytes se non lo è, prendendo in bytes anche la lunghezza del messaggio
    def send(self, message):
        if not isinstance(message, bytes):
            message = message.encode()
            message = int.to_bytes(len(message), 2, 'big') + message
        self.__socket.sendall(message) # invia poi il messaggio

    # con questa funzione, utilizza prima il socket per recuperare prima le dimensioni del messaggio, se la lunghezza del messaggio
    # non è 0, allora recupera il resto del messaggio usando recv e lo codifica(la prima chiamata recupera solo la possibile dimensione)
    def receive(self):
        length = int.from_bytes(self.__socket.recv(2), 'big')
        if length == 0:
            return None
        return self.__socket.recv(length).decode()
    
    def close(self):
        self.__socket.close()
        if not self.__notify_closed:
            self.on_event('close')
            self.__notify_closed = True

    def __handle_incoming_messages(self):
        try:
            while not self.closed:
                message = self.receive()
                if message is None:
                    break
                self.on_event('message', message)
        except Exception as e:
            if self.closed and isinstance(e, OSError):
                return # silently ignore error, because this is simply the socket being closed locally
            self.on_event('error', error=e)
        finally:
            self.close()

    def on_event(self, event: str, payload: str=None, connection: 'Connection'=None, error: Exception=None):
        if connection is None:
            connection = self
        self.callback(event, payload, connection, error)


# classe per i clienti
class Client(Connection):
    def __init__(self, server_address, callback=None):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(address(port=0))
        sock.connect(address(*server_address)) # questo per connettersi ad un server (metto la * perchè server_address è una tupla con IP e port)
        super().__init__(sock, callback)


# classe per il server TCP
# Il server è quello che aspetta stando in ascolto per possibili nuove connessioni
# aspetta e le accetta, per poi cominciare ad inviare e ricevere dati
class Server:
    def __init__(self, port, callback=None):
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.bind(address(port=port))
        self.__listener_thread = threading.Thread(target=self.__handle_incoming_connections, daemon=True)
        self.__callback = callback
        if self.__callback:
            self.__listener_thread.start()

    @property
    def callback(self):
        return self.__callback or (lambda *_: None)
    
    @callback.setter
    def callback(self, value):
        if self.__callback:
            raise ValueError("Callback can only be set once")
        self.__callback = value
        if value:
            self.__listener_thread.start()
    
    def __handle_incoming_connections(self):
        self.__socket.listen() # listen serve per poter fare sì che il server accetti connessioni in arrivo (posso anche metterci un numero per indicare quante ne aspetto)
        self.on_event('listen', address=self.__socket.getsockname())
        try:
            while not self.__socket._closed:
                socket, address = self.__socket.accept() # con questo si accetta una nuova connessione
                connection = Connection(socket)
                self.on_event('connect', connection, address)
        except ConnectionAbortedError as e:
            pass # silently ignore error, because this is simply the socket being closed locally
        except Exception as e:
            self.on_event('error', error=e)
        finally:
            self.on_event('stop')

    def on_event(self, event: str, connection: Connection=None, address: tuple=None, error: Exception=None):
        self.__callback(event, connection, address, error)

    def close(self):
        self.__socket.close()
