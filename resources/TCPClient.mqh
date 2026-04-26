#ifndef __SOCKET_TCPCLIENT_MQH__
#define __SOCKET_TCPCLIENT_MQH__

#define INVALID_SOCKET   -1
#define SOCKET_ERROR     -1
#define AF_INET          2
#define SOCK_STREAM      1
#define IPPROTO_TCP      6
#define FIONBIO          0x8004667E
#define WSAEWOULDBLOCK   10035
#define MIN_RECONNECT_MS 250

struct sockaddr_in {
   short  sin_family;
   ushort sin_port;
   uint   sin_addr;
   uchar  sin_zero[8];
};

#import "ws2_32.dll"
int    WSAStartup(ushort wVersionRequested, uchar &lpWSAData[]);
int    WSACleanup();
int    socket(int af, int type, int protocol);
int    connect(int s, uchar &name[], int namelen);
int    closesocket(int s);
int    ioctlsocket(int s, uint cmd, uint &argp);
int    send(int s, uchar &buf[], int len, int flags);
int    recv(int s, uchar &buf[], int len, int flags);
uint   inet_addr(uchar &cp[]);
ushort htons(ushort hostshort);
int    WSAGetLastError();
#import

class CTcpClient {
 private:
   string m_host;
   ushort m_port;
   int    m_reconnectMs;

   bool m_initialized;
   bool m_wsaReady;
   bool m_connected;
   int  m_socket;

   uint   m_nextReconnectMs;
   string m_rxBuffer;
   string m_lastError;

   uchar  m_wsadata[];
   string m_lineQueue[];

   uint NowMs() const {
      return GetTickCount();
   }

   bool IsReached(const uint now, const uint target) const {
      return ((int)(now - target) >= 0);
   }

   void SetLastError(const string value) {
      m_lastError = value;
   }

   void EnqueueLine(const string line) {
      int size = ArraySize(m_lineQueue);
      ArrayResize(m_lineQueue, size + 1);
      m_lineQueue[size] = line;
   }

   void ScheduleReconnect() {
      int delay         = MathMax(m_reconnectMs, MIN_RECONNECT_MS);
      m_nextReconnectMs = NowMs() + (uint)delay;
   }

   void CloseSocketIfNeeded() {
      if(m_socket != INVALID_SOCKET) {
         closesocket(m_socket);
         m_socket = INVALID_SOCKET;
      }
   }

   bool EnsureWinsock() {
      if(m_wsaReady)
         return true;

      ArrayResize(m_wsadata, 512);
      int rc = WSAStartup(0x0202, m_wsadata);
      if(rc != 0) {
         SetLastError(StringFormat("WSAStartup failed (%d)", rc));
         PrintFormat("CTcpClient: WSAStartup falhou. rc=%d", rc);
         return false;
      }

      m_wsaReady = true;
      return true;
   }

   bool SetNonBlocking() {
      uint mode = 1;
      int  rc   = ioctlsocket(m_socket, FIONBIO, mode);
      if(rc == SOCKET_ERROR) {
         int err = WSAGetLastError();
         SetLastError(StringFormat("ioctlsocket failed (%d)", err));
         PrintFormat("CTcpClient: nao foi possivel ativar non-blocking. err=%d", err);
         return false;
      }
      return true;
   }

   void Disconnect(const string reason) {
      if(m_connected || m_socket != INVALID_SOCKET)
         PrintFormat("CTcpClient: desconectado (%s)", reason);

      SetLastError(reason);
      m_connected = false;
      CloseSocketIfNeeded();

      if(m_initialized)
         ScheduleReconnect();
   }

   bool ConnectSocket() {
      if(!EnsureWinsock()) {
         ScheduleReconnect();
         return false;
      }

      CloseSocketIfNeeded();
      m_socket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
      if(m_socket == INVALID_SOCKET) {
         int err = WSAGetLastError();
         SetLastError(StringFormat("socket failed (%d)", err));
         PrintFormat("CTcpClient: socket() falhou. err=%d", err);
         ScheduleReconnect();
         return false;
      }

      uchar hostBytes[];
      StringToCharArray(m_host, hostBytes, 0, WHOLE_ARRAY, CP_ACP);
      uint rawIp = inet_addr(hostBytes);
      if(rawIp == 0xFFFFFFFF) {
         SetLastError("invalid_host");
         PrintFormat("CTcpClient: host invalido: %s", m_host);
         CloseSocketIfNeeded();
         ScheduleReconnect();
         return false;
      }

      sockaddr_in addr;
      addr.sin_family = AF_INET;
      addr.sin_port   = htons(m_port);
      addr.sin_addr   = rawIp;
      ArrayInitialize(addr.sin_zero, 0);

      uchar rawAddr[];
      ArrayResize(rawAddr, 16);
      StructToCharArray(addr, rawAddr, 0);

      int rc = connect(m_socket, rawAddr, 16);
      if(rc == SOCKET_ERROR) {
         int err = WSAGetLastError();
         SetLastError(StringFormat("connect failed (%d)", err));
         PrintFormat(
             "CTcpClient: connect falhou host=%s port=%d err=%d",
             m_host,
             (int)m_port,
             err);
         CloseSocketIfNeeded();
         ScheduleReconnect();
         return false;
      }

      if(!SetNonBlocking()) {
         Disconnect("set_non_blocking_failed");
         return false;
      }

      m_connected = true;
      m_rxBuffer  = "";
      SetLastError("");
      PrintFormat("CTcpClient: conectado em %s:%d", m_host, (int)m_port);
      return true;
   }

   void DrainIncoming() {
      while(m_connected && m_socket != INVALID_SOCKET) {
         uchar buffer[];
         ArrayResize(buffer, 2048);

         int received = recv(m_socket, buffer, 2048, 0);
         if(received > 0) {
            m_rxBuffer += CharArrayToString(buffer, 0, received, CP_UTF8);

            while(true) {
               int nl = StringFind(m_rxBuffer, "\n");
               if(nl < 0)
                  break;

               string line = StringSubstr(m_rxBuffer, 0, nl);
               m_rxBuffer  = StringSubstr(m_rxBuffer, nl + 1);
               EnqueueLine(line);
            }
            continue;
         }

         if(received == 0) {
            Disconnect("server_closed_connection");
            break;
         }

         int err = WSAGetLastError();
         if(err == WSAEWOULDBLOCK)
            break;

         Disconnect(StringFormat("recv_error_%d", err));
         break;
      }
   }

 public:
   CTcpClient(void) {
      m_host            = "";
      m_port            = 0;
      m_reconnectMs     = 2000;
      m_initialized     = false;
      m_wsaReady        = false;
      m_connected       = false;
      m_socket          = INVALID_SOCKET;
      m_nextReconnectMs = 0;
      m_rxBuffer        = "";
      m_lastError       = "";
      ArrayResize(m_wsadata, 0);
      ArrayResize(m_lineQueue, 0);
   }

   bool Init(const string host, const ushort port, const int reconnect_ms) {
      Shutdown();

      m_host        = host;
      m_port        = port;
      m_reconnectMs = reconnect_ms;

      m_initialized = true;
      if(!EnsureWinsock()) {
         m_initialized = false;
         return false;
      }

      m_nextReconnectMs = NowMs();
      return true;
   }

   void Shutdown() {
      m_initialized = false;
      m_connected   = false;
      CloseSocketIfNeeded();
      m_rxBuffer  = "";
      m_lastError = "";
      ArrayResize(m_lineQueue, 0);

      if(m_wsaReady) {
         WSACleanup();
         m_wsaReady = false;
      }
   }

   void Pump() {
      if(!m_initialized)
         return;

      uint now = NowMs();
      if(!m_connected) {
         if(IsReached(now, m_nextReconnectMs))
            ConnectSocket();
         return;
      }

      DrainIncoming();
   }

   bool IsConnected() const {
      return m_connected;
   }

   bool SendLine(const string line) {
      if(!m_connected || m_socket == INVALID_SOCKET) {
         SetLastError("not_connected");
         return false;
      }

      uchar data[];
      int   size = StringToCharArray(line, data, 0, WHOLE_ARRAY, CP_UTF8);
      if(size <= 1) {
         SetLastError("empty_payload");
         return false;
      }

      int total     = size - 1;
      int sentTotal = 0;

      while(sentTotal < total) {
         int   remaining = total - sentTotal;
         uchar chunk[];
         ArrayResize(chunk, remaining);
         ArrayCopy(chunk, data, 0, sentTotal, remaining);

         int sent = send(m_socket, chunk, remaining, 0);
         if(sent == SOCKET_ERROR) {
            int err = WSAGetLastError();
            if(err == WSAEWOULDBLOCK)
               return true;

            Disconnect(StringFormat("send_error_%d", err));
            return false;
         }

         if(sent <= 0) {
            Disconnect("send_returned_zero_or_negative");
            return false;
         }

         sentTotal += sent;
      }

      SetLastError("");
      return true;
   }

   bool TryReadLine(string &line) {
      int size = ArraySize(m_lineQueue);
      if(size <= 0)
         return false;

      line = m_lineQueue[0];
      for(int i = 1; i < size; i++)
         m_lineQueue[i - 1] = m_lineQueue[i];

      ArrayResize(m_lineQueue, size - 1);
      return true;
   }

   string LastError() const {
      return m_lastError;
   }
};

#endif   // __SOCKET_TCPCLIENT_MQH__
