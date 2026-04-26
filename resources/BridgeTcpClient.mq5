//+------------------------------------------------------------------+
//|                                                BridgeTcpClient.mq5|
//|                             Pure TCP bridge (tester/local only)   |
//+------------------------------------------------------------------+
#property strict
#property version "1.00"
#property copyright "Local"
#property link "https://www.mql5.com"

#include <Socket/TCPClient.mqh>
#include <Trade/Trade.mqh>

input string InpServerHost       = "127.0.0.1";
input ushort InpServerPort       = 47001;
input bool   InpTesterOnly       = true;
input int    InpHeartbeatSeconds = 1;
input int    InpReconnectMs      = 2000;

bool       g_active          = false;
bool       g_wasConnected    = false;
uint       g_lastHeartbeatMs = 0;
CTcpClient g_client;
CTrade     g_trade;

class IMessageCommand;
IMessageCommand *g_commands[];

uint NowMs() {
   return GetTickCount();
}

long EpochMs() {
   return (long)TimeGMT() * 1000;
}

string TrimCopy(string value) {
   StringTrimLeft(value);
   StringTrimRight(value);
   return value;
}

bool TryGetFieldByDelimiter(const string source, const string key, const ushort delimiter, string &value) {
   string parts[];
   int    count = StringSplit(source, delimiter, parts);
   for(int i = 0; i < count; i++) {
      string token = TrimCopy(parts[i]);
      if(token == "")
         continue;

      int eq = StringFind(token, "=");
      if(eq <= 0)
         continue;

      string tokenKey   = TrimCopy(StringSubstr(token, 0, eq));
      string tokenValue = TrimCopy(StringSubstr(token, eq + 1));
      if(StringCompare(tokenKey, key, false) == 0) {
         value = tokenValue;
         return true;
      }
   }

   return false;
}

bool TryGetField(const string line, const string key, string &value) {
   return TryGetFieldByDelimiter(line, key, ';', value);
}

bool TryGetPayloadField(const string payload, const string key, string &value) {
   if(TryGetFieldByDelimiter(payload, key, ';', value))
      return true;
   if(TryGetFieldByDelimiter(payload, key, ',', value))
      return true;
   if(TryGetFieldByDelimiter(payload, key, '&', value))
      return true;

   return false;
}

bool ExtractField(const string line, const string payload, const string key, string &value) {
   if(TryGetField(line, key, value))
      return true;
   if(payload != "" && TryGetPayloadField(payload, key, value))
      return true;

   return false;
}

bool TryGetDoubleFromMessage(const string line, const string payload, const string key, double &value) {
   string raw;
   if(!ExtractField(line, payload, key, raw))
      return false;

   raw = TrimCopy(raw);
   if(raw == "")
      return false;

   value = StringToDouble(raw);
   return true;
}

bool TryGetLongFromMessage(const string line, const string payload, const string key, long &value) {
   string raw;
   if(!ExtractField(line, payload, key, raw))
      return false;

   raw = TrimCopy(raw);
   if(raw == "")
      return false;

   value = StringToInteger(raw);
   return true;
}

bool SendLine(const string line) {
   bool ok = g_client.SendLine(line);
   if(!ok) {
      string err = g_client.LastError();
      if(err != "")
         PrintFormat("BridgeTcpClient: send failed (%s)", err);
   }

   return ok;
}

void SendCommandResult(const string command, const string status, const string message) {
   SendLine(StringFormat("type=command_result;command=%s;status=%s;message=%s;ts=%I64d\n", command, status, message, EpochMs()));
}

void SendHello() {
   string mode = ((bool)MQLInfoInteger(MQL_TESTER)) ? "tester" : "live";
   string msg  = StringFormat(
       "type=hello;client=mt5;mode=%s;version=1;ts=%I64d\n",
       mode,
       EpochMs());
   SendLine(msg);
}

void SendHeartbeat() {
   string msg = StringFormat("type=heartbeat;ts=%I64d\n", EpochMs());
   if(SendLine(msg))
      g_lastHeartbeatMs = NowMs();
}

void SendHeartbeatAck(const string ts) {
   SendLine(StringFormat("type=heartbeat_ack;ts=%s\n", ts));
}

void SendError(const string reason) {
   SendLine(StringFormat("type=error;reason=%s;ts=%I64d\n", reason, EpochMs()));
}

double NormalizeVolumeToSymbol(const string symbol, double volume) {
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0)
      step = 0.01;

   double minVol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   if(minVol <= 0.0)
      minVol = step;

   double maxVol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   if(maxVol <= 0.0)
      maxVol = 100.0;

   if(volume <= 0.0)
      volume = minVol;

   volume = MathMax(volume, minVol);
   volume = MathMin(volume, maxVol);
   volume = MathRound(volume / step) * step;

   return volume;
}

void SendOpenPositionsSnapshot() {
   if(!g_client.IsConnected())
      return;

   int total = PositionsTotal();
   if(total <= 0) {
      SendLine(StringFormat("type=positions;payload=no positions;ts=%I64d\n", EpochMs()));
      return;
   }

   string payloadList = "";
   int    collected   = 0;
   for(int i = 0; i < total; i++) {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      string symbol  = PositionGetString(POSITION_SYMBOL);
      long   posType = PositionGetInteger(POSITION_TYPE);
      double volume  = PositionGetDouble(POSITION_VOLUME);
      double price   = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl      = PositionGetDouble(POSITION_SL);
      double tp      = PositionGetDouble(POSITION_TP);
      double profit  = PositionGetDouble(POSITION_PROFIT);
      long   timeMsc = (long)PositionGetInteger(POSITION_TIME_MSC);
      int    digits  = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      string side    = (posType == POSITION_TYPE_BUY) ? "buy" : "sell";

      if(timeMsc <= 0)
         timeMsc = (long)PositionGetInteger(POSITION_TIME) * 1000;
      if(digits <= 0)
         digits = _Digits;

      string payload = StringFormat(
          "ticket=%I64u,symbol=%s,side=%s,volume=%s,open_price=%s,sl=%s,tp=%s,profit=%s,time_msc=%I64d",
          ticket,
          symbol,
          side,
          DoubleToString(volume, 2),
          DoubleToString(price, digits),
          DoubleToString(sl, digits),
          DoubleToString(tp, digits),
          DoubleToString(profit, 2),
          timeMsc);

      if(collected > 0)
         payloadList += "|";
      payloadList += payload;
      collected++;
   }

   if(collected <= 0)
      SendLine(StringFormat("type=positions;payload=positions not found;ts=%I64d\n", EpochMs()));
   else
      SendLine(StringFormat("type=positions;count=%d;payload=%s;ts=%I64d\n", collected, payloadList, EpochMs()));
}

class IMessageCommand {
 public:
   virtual string Type() const                                     = 0;
   virtual void   Execute(const string line, const string payload) = 0;
};

class CHelloAckCommand : public IMessageCommand {
 public:
   string Type() const {
      return "hello_ack";
   }

   void Execute(const string line, const string payload) {
      PrintFormat("BridgeTcpClient: hello_ack received: %s", line);
   }
};

class CHeartbeatCommand : public IMessageCommand {
 public:
   string Type() const {
      return "heartbeat";
   }

   void Execute(const string line, const string payload) {
      string ts;
      if(!ExtractField(line, payload, "ts", ts))
         ts = (string)EpochMs();
      SendHeartbeatAck(ts);
   }
};

class CHeartbeatAckCommand : public IMessageCommand {
 public:
   string Type() const {
      return "heartbeat_ack";
   }

   void Execute(const string line, const string payload) {
   }
};

class CErrorCommand : public IMessageCommand {
 public:
   string Type() const {
      return "error";
   }

   void Execute(const string line, const string payload) {
      PrintFormat("BridgeTcpClient: error returned by server: %s", line);
   }
};

class CBuyCommand : public IMessageCommand {
 public:
   string Type() const {
      return "buy";
   }

   void Execute(const string line, const string payload) {
      string symbol = _Symbol;
      ExtractField(line, payload, "symbol", symbol);
      symbol = TrimCopy(symbol);
      if(symbol == "")
         symbol = _Symbol;

      double volume = 0.0;
      TryGetDoubleFromMessage(line, payload, "volume", volume);
      volume = NormalizeVolumeToSymbol(symbol, volume);

      double sl = 0.0;
      double tp = 0.0;
      TryGetDoubleFromMessage(line, payload, "sl", sl);
      TryGetDoubleFromMessage(line, payload, "tp", tp);

      string comment = "BridgeTcpClient";
      ExtractField(line, payload, "comment", comment);

      long deviation = 20;
      TryGetLongFromMessage(line, payload, "deviation", deviation);
      g_trade.SetDeviationInPoints((int)MathMax(deviation, 0));

      bool ok = g_trade.Buy(volume, symbol, 0.0, sl, tp, comment);
      if(ok) {
         SendCommandResult("buy", "ok", StringFormat("symbol=%s volume=%s", symbol, DoubleToString(volume, 2)));
      } else {
         SendCommandResult("buy", "failed", StringFormat("retcode=%u;desc=%s", (uint)g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
      }
   }
};

class CSellCommand : public IMessageCommand {
 public:
   string Type() const {
      return "sell";
   }

   void Execute(const string line, const string payload) {
      string symbol = _Symbol;
      ExtractField(line, payload, "symbol", symbol);
      symbol = TrimCopy(symbol);
      if(symbol == "")
         symbol = _Symbol;

      double volume = 0.0;
      TryGetDoubleFromMessage(line, payload, "volume", volume);
      volume = NormalizeVolumeToSymbol(symbol, volume);

      double sl = 0.0;
      double tp = 0.0;
      TryGetDoubleFromMessage(line, payload, "sl", sl);
      TryGetDoubleFromMessage(line, payload, "tp", tp);

      string comment = "BridgeTcpClient";
      ExtractField(line, payload, "comment", comment);

      long deviation = 20;
      TryGetLongFromMessage(line, payload, "deviation", deviation);
      g_trade.SetDeviationInPoints((int)MathMax(deviation, 0));

      bool ok = g_trade.Sell(volume, symbol, 0.0, sl, tp, comment);
      if(ok) {
         SendCommandResult("sell", "ok", StringFormat("symbol=%s volume=%s", symbol, DoubleToString(volume, 2)));
      } else {
         SendCommandResult("sell", "failed", StringFormat("retcode=%u;desc=%s", (uint)g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
      }
   }
};

class CCloseAllCommand : public IMessageCommand {
 public:
   string Type() const {
      return "close_all";
   }

   void Execute(const string line, const string payload) {
      string symbolFilter = "";
      ExtractField(line, payload, "symbol", symbolFilter);
      symbolFilter = TrimCopy(symbolFilter);

      int closed   = 0;
      int failed   = 0;
      int targeted = 0;

      for(int i = PositionsTotal() - 1; i >= 0; i--) {
         ulong ticket = PositionGetTicket(i);
         if(ticket == 0)
            continue;

         string symbol = PositionGetString(POSITION_SYMBOL);
         if(symbolFilter != "" && StringCompare(symbol, symbolFilter, false) != 0)
            continue;

         targeted++;
         if(g_trade.PositionClose(ticket))
            closed++;
         else
            failed++;
      }

      if(targeted <= 0) {
         SendCommandResult("close_all", "ok", "no positions");
         return;
      }

      if(failed == 0) {
         SendCommandResult("close_all", "ok", StringFormat("closed=%d", closed));
      } else {
         SendCommandResult("close_all", "partial", StringFormat("closed=%d;failed=%d", closed, failed));
      }
   }
};

class CClosePositionCommand : public IMessageCommand {
 public:
   string Type() const {
      return "close_position";
   }

   void Execute(const string line, const string payload) {
      long ticketValue = 0;
      bool hasTicket   = TryGetLongFromMessage(line, payload, "ticket", ticketValue) && ticketValue > 0;

      string symbol = "";
      ExtractField(line, payload, "symbol", symbol);
      symbol = TrimCopy(symbol);

      bool ok = false;
      if(hasTicket) {
         ok = g_trade.PositionClose((ulong)ticketValue);
         if(ok) {
            SendCommandResult("close_position", "ok", StringFormat("ticket=%I64d", ticketValue));
         } else {
            SendCommandResult("close_position", "failed", StringFormat("ticket=%I64d;retcode=%u;desc=%s", ticketValue, (uint)g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
         }
         return;
      }

      if(symbol != "") {
         ok = g_trade.PositionClose(symbol);
         if(ok) {
            SendCommandResult("close_position", "ok", StringFormat("symbol=%s", symbol));
         } else {
            SendCommandResult("close_position", "failed", StringFormat("symbol=%s;retcode=%u;desc=%s", symbol, (uint)g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription()));
         }
         return;
      }

      SendCommandResult("close_position", "failed", "missing ticket or symbol");
   }
};

void RegisterCommand(IMessageCommand *command) {
   if(CheckPointer(command) != POINTER_DYNAMIC)
      return;

   int size = ArraySize(g_commands);
   ArrayResize(g_commands, size + 1);
   g_commands[size] = command;
}

void ReleaseCommands() {
   int size = ArraySize(g_commands);
   for(int i = 0; i < size; i++) {
      if(CheckPointer(g_commands[i]) == POINTER_DYNAMIC)
         delete g_commands[i];
   }

   ArrayResize(g_commands, 0);
}

void InitializeCommands() {
   ReleaseCommands();

   RegisterCommand(new CHelloAckCommand());
   RegisterCommand(new CHeartbeatCommand());
   RegisterCommand(new CHeartbeatAckCommand());
   RegisterCommand(new CErrorCommand());
   RegisterCommand(new CBuyCommand());
   RegisterCommand(new CSellCommand());
   RegisterCommand(new CCloseAllCommand());
   RegisterCommand(new CClosePositionCommand());
}

bool DispatchCommand(const string msgType, const string line, const string payload) {
   int size = ArraySize(g_commands);
   for(int i = 0; i < size; i++) {
      if(StringCompare(g_commands[i].Type(), msgType, false) == 0) {
         g_commands[i].Execute(line, payload);
         return true;
      }
   }

   return false;
}

bool TryParseIncomingMessage(const string line, string &msgType, string &payload) {
   if(!TryGetField(line, "type", msgType))
      return false;

   if(!TryGetField(line, "payload", payload))
      payload = "";

   return true;
}

void HandleIncomingLine(const string line) {
   string msgType;
   string payload;
   if(!TryParseIncomingMessage(line, msgType, payload)) {
      SendError("missing_type");
      return;
   }

   if(!DispatchCommand(msgType, line, payload))
      SendError("unsupported_type");
}

void MaintainConnectionAndRead() {
   if(!g_active)
      return;

   g_client.Pump();

   bool connected = g_client.IsConnected();
   if(!g_wasConnected && connected) {
      PrintFormat("BridgeTcpClient: connected to %s:%d", InpServerHost, (int)InpServerPort);
      SendHello();
      g_lastHeartbeatMs = 0;
   }

   g_wasConnected = connected;

   string line;
   while(g_client.TryReadLine(line)) {
      line = TrimCopy(line);
      if(line == "")
         continue;
      HandleIncomingLine(line);
   }

   if(!connected)
      return;

   uint now = NowMs();
   if(InpHeartbeatSeconds > 0) {
      uint hbEveryMs = (uint)InpHeartbeatSeconds * 1000;
      if(g_lastHeartbeatMs == 0 || now - g_lastHeartbeatMs >= hbEveryMs)
         SendHeartbeat();
   }
}

int OnInit() {
   if(InpTesterOnly && !(bool)MQLInfoInteger(MQL_TESTER)) {
      Print("BridgeTcpClient: outside Strategy Tester. client disabled.");
      g_active = false;
      return INIT_SUCCEEDED;
   }

   if(!MQLInfoInteger(MQL_DLLS_ALLOWED)) {
      Print("BridgeTcpClient: enable 'Allow DLL imports'.");
      return INIT_FAILED;
   }

   g_active          = true;
   g_wasConnected    = false;
   g_lastHeartbeatMs = 0;

   if(!g_client.Init(InpServerHost, InpServerPort, InpReconnectMs)) {
      PrintFormat("BridgeTcpClient: failed to initialize TCP client (%s)", g_client.LastError());
      g_active = false;
      return INIT_FAILED;
   }

   InitializeCommands();
   EventSetTimer(1);
   PrintFormat(
       "BridgeTcpClient: started host=%s port=%d tester=%s",
       InpServerHost,
       (int)InpServerPort,
       ((bool)MQLInfoInteger(MQL_TESTER) ? "true" : "false"));

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   EventKillTimer();
   ReleaseCommands();
   g_client.Shutdown();
   g_active       = false;
   g_wasConnected = false;
}

void OnTick() {
   MaintainConnectionAndRead();

   if(!g_active || !g_client.IsConnected())
      return;

   SendOpenPositionsSnapshot();
}

void OnTimer() {
   MaintainConnectionAndRead();
}
