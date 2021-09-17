from leviot.utils.usyslog import UDPClient as SyslogClient, SyslogClient as DummyClient
from leviot import conf

mqtt = None

def set_mqtt(mqttctrl):
    global mqtt
    mqtt = mqttctrl


class Logger:
    def __init__(self, tag):
        self.tag = tag
        self.syslog = None
        try:
            if conf.syslog:
                self.syslog = SyslogClient(ip='192.168.1.157')
        except Exception as ex:
            self._print_and_mqtt("DEBUG: Cannot connect to {} SysLog server".format(conf.syslog))
        
        if not self.syslog:
            self.syslog = DummyClient()

    @staticmethod
    def _print_and_mqtt(message: str):
        print("$$  " + message)
        if mqtt is not None:
            mqtt.log(message)

    def d(self, message):
        self._print_and_mqtt("DEBUG {}: {}".format(self.tag, message))
        self.syslog.debug("{}: {}".format(self.tag, message))

    def i(self, message):
        self._print_and_mqtt("INFO  {}: {}".format(self.tag, message))
        self.syslog.info("{}: {}".format(self.tag, message))

    def w(self, message):
        self._print_and_mqtt("WARN  {}: {}".format(self.tag, str(message)))
        self.syslog.warning("{}: {}".format(self.tag, message))

    def e(self, message):
        self._print_and_mqtt("ERROR {}: {}".format(self.tag, str(message)))
        self.syslog.error("{}: {}".format(self.tag, message))
