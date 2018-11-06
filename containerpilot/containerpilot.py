import sys
from functools import partial
import os
import subprocess
import signal
from string import Template

import consul
import netifaces

# command = None


# def signal_handler(signal, frame):
#     print("Docker is stopping")
#     global command
#     command.stop()


def register_service():
    service_name = 'test'
    service_id = "{}-{}".format(service_name, os.environ.get('HOSTNAME'))
    client = consul.Consul(host='172.17.0.1')

    client.agent.service.register(service_name,
                                  service_id=service_id,
                                  port=8080,
                                  check=consul.Check.script('/bin/true', 10))


def deregister_service():
    service_name = 'test'
    service_id = "{}-{}".format(service_name, os.environ.get('HOSTNAME'))
    client = consul.Consul(host='172.17.0.1')
    client.agent.service.deregister(service_id)


def register_check():
    pass


def deregister_check():
    pass


def main(argv):

    # global command
    # service.run_command()
    autopilot = Autopilot(argv)
    try:
        autopilot.run()
    except Exception as ex:
        print("Autopilot error, quiting")
        print(ex)
        exit(2)
    # command = Command(argv[1:])
    # command.run()


class Command(object):
    arguments = []

    def __init__(self, argv, env):
        self.arguments = argv
        self.proc = None
        self.env = env

    def run(self):
        print(self.arguments)
        self.proc = subprocess.Popen(self.arguments, env=self.env)
        self.register_signals()
        # register_service()
        # try:
        #     outs, errs = self.proc.communicate()
        # except subprocess.SubprocessError:
        #     self.proc.kill()
        #     outs, errs = self.proc.communicate()
        # # deregister_service()
        return self.proc

    def register_signals(self):
        """
        Function to forward signals
        :return:
        """
        def forward_signal_to_child(pid, signum, frame):
            os.kill(pid, signum)

        signal.signal(signal.SIGINT, partial(forward_signal_to_child, self.proc.pid))
        signal.signal(signal.SIGTERM, partial(forward_signal_to_child, self.proc.pid))
        signal.signal(signal.SIGHUP, partial(forward_signal_to_child, self.proc.pid))
        signal.signal(signal.SIGQUIT, partial(forward_signal_to_child, self.proc.pid))
        signal.signal(signal.SIGUSR1, partial(forward_signal_to_child, self.proc.pid))

    def stop(self):
        # deregister_service()
        self.proc.terminate()


class AutopilotConfigException(Exception):
    pass


class AutopilotCheckConfigException(Exception):
    pass


class Autopilot(object):

    def __init__(self, argv):
        self.argv = argv
        self.host = None
        self.name = None
        self.port = None
        self.check_script = None
        self.check_http = None
        self.check_interval = None
        self.tags = []
        self.wan_ip = None
        # must be consul host set before consul manipulation
        self._set_consul_host()
        self.env = os.environ.copy()
        self._set_cleaned_env()
        self._load_config()
        self._set_wan_ip()

    def _pre_start(self):
        pass

    def run(self):
        self._pre_start()

        command = Command(self.argv[1:], self._set_cleaned_env())
        proc = command.run()
        self._register_service()
        try:
            retcode = proc.wait()
        except subprocess.SubprocessError:
            print("Subprocess error")
            proc.kill()
            retcode = proc.wait()
        self._deregister_service()

        self._post_start()
        exit(retcode)

    def _post_start(self):
        pass

    def _set_consul_host(self):
        self.host = netifaces.gateways()['default'][netifaces.AF_INET][0]

    def _set_wan_ip(self):
        client = consul.Consul(host=self.host)
        try:
            self.wan_ip = client.agent.self()['Member']['Addr']
        except KeyError:
            pass

    def _load_check_config(self):
        check_loaded = False

        try:
            self.check_script = self.env.get('AUTOPILOT_CHECK_SCRIPT')
            self.check_interval = self.env.get('AUTOPILOT_CHECK_INTERVAL')
            check_loaded = True
        except KeyError:
            pass

        if not check_loaded:
            try:
                self.check_http = self.env.get('AUTOPILOT_CHECK_HTTP')
                self.check_interval = self.env.get('AUTOPILOT_CHECK_INTERVAL')
                check_loaded = True
            except KeyError:
                pass

        if not check_loaded:
            raise AutopilotCheckConfigException()

    def _load_config(self):
        try:
            self.name = self.env.get('AUTOPILOT_NAME')
            self.port = int(self.env.get('AUTOPILOT_PORT'))
        except KeyError:
            raise AutopilotConfigException()

        self._load_check_config()

        try:
            self.tags = self.env.get('AUTOPILOT_TAGS').split()
        except KeyError:
            pass

    def _set_cleaned_env(self):
        cleaned_env = self.env.copy()
        for key, value in os.environ.items():
            if key.startswith("AUTOPILOT_"):
                cleaned_env.pop(key)
        self.cleaned_env = cleaned_env

    def _check_substitution(self, text):
        # dictionary with variables which can be substituted in check definition
        variables = dict(wan_ip=self.wan_ip,
                         port=self.port)
        template = Template(text)
        try:
            cleaned_text = template.substitute(variables)
            return cleaned_text
        except ValueError:
            raise AutopilotCheckConfigException("Cannot substitute check definition")

    def _get_service_check(self):
        check = None
        if self.check_script:
            check = consul.Check.script(self._check_substitution(self.check_script), self.check_interval)
        elif self.check_http:
            check = consul.Check.http(self._check_substitution(self.check_http), self.check_interval)
        else:
            raise AutopilotConfigException()
        return check

    def _get_service_id(self):
        try:
            service_id = "{}-{}:{}".format(self.name, self.env.get('HOSTNAME'), self.port)
        except KeyError:
            import socket
            hostname = socket.gethostbyaddr(socket.gethostname())[0]
            service_id = "{}-{}:{}".format(self.name, hostname, self.port)
        return service_id

    def _register_service(self):
        # print("Registering service")
        service_id = self._get_service_id()
        client = consul.Consul(host=self.host)

        try:
            client.agent.service.register(self.name,
                                          service_id=service_id,
                                          port=self.port,
                                          check=self._get_service_check(),
                                          tags=self.tags)
        except consul.ConsulException as ex:
            print("Cannot register the service: {}".format(str(ex)))

    def _deregister_service(self):
        # print("Deregistering service")
        service_id = self._get_service_id()
        client = consul.Consul(host=self.host)
        try:
            client.agent.service.deregister(service_id)
        except consul.ConsulException as ex:
            print("Cannot deregister the service: {}".format(str(ex)))


if __name__ == "__main__":
    main(sys.argv)
