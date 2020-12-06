import binascii
import pyshark
import re
import requests

# Temporary.
from ip2geotools.databases.noncommercial import DbIpCity


class WhomstCapture(object):
    def __init__(self, interface=None, bpf_filter=None):
        self.capture = None

        self.interface = interface
        self.bpf_filter = bpf_filter

        self.re_display_name = re.compile(r'"displayName":"([^"]*)"')
        self.re_connect_code = re.compile(r'"connectCode":"([^"]*)"')
        self.re_address = re.compile(r'"oppAddress":"([^"]*)"')


    def post_whomst(self, display_name, connect_code, ip_address, region):
        json = {
            'display_name': display_name,
            'connect_code': connect_code,
            'ip_address': ip_address,
            'region': region
        }
        requests.post('https://kneise.eu/whomst/insert', json=json)


    def sniff_continuously(self):
        self.capture = pyshark.LiveCapture(self.interface, self.bpf_filter)
        print('Waiting for Slippi game...')

        for packet in self.capture.sniff_continuously():
            try:
                packet_content = binascii.unhexlify(packet.data.data)
            except AttributeError:
                continue

            if b"get-ticket-resp" in packet_content:
                display_name = re.search(self.re_display_name, str(packet_content)).group(1)
                connect_code = re.search(self.re_connect_code, str(packet_content)).group(1)
                ip_address = re.search(self.re_address, str(packet_content)).group(1).partition(':')[0]

                # Temporary.
                r = DbIpCity.get(ip_address, api_key='free')
                region = r.region
                country = r.country

                print('Opponent:')
                print('  Display name:  %s' % display_name)
                print('  Connect code:  %s' % connect_code)
                print('  IP-address:    %s' % ip_address)
                print('  From:          %s, %s' % (r.region, r.country))

                self.post_whomst(display_name, connect_code, ip_address, r.region + ', ' + r.country)                


if __name__ == '__main__':
    bpf_filter = 'udp'
    bpf_filter += ' and not ip broadcast'
    bpf_filter += ' and not ip multicast'
    bpf_filter += ' and len > 100'

    capture = WhomstCapture(bpf_filter=bpf_filter)
    capture.sniff_continuously()

