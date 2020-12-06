#include <stdio.h>
#include <tins/tins.h>
#include <string>

using namespace Tins;

bool sniff_callback(const PDU &pdu)
{
    const IP &ip = pdu.rfind_pdu<IP>(); 
    const UDP &udp = pdu.rfind_pdu<UDP>();

    const RawPDU &raw = udp.rfind_pdu<RawPDU>();
    const RawPDU::payload_type &payload = raw.payload();
    std::string payload_str(payload.begin(), payload.end());

    printf("%s\n", payload_str.c_str());

    return true;
}

int main(int argc, char *argv[])
{
    const NetworkInterface &default_interface = NetworkInterface::default_interface();

    SnifferConfiguration sniffer_config;
    sniffer_config.set_filter("udp and not ip broadcast and not ip multicast");
    sniffer_config.set_promisc_mode(true);
    sniffer_config.set_immediate_mode(true);

    Sniffer sniffer(default_interface.name(), sniffer_config);
    sniffer.sniff_loop(sniff_callback);
}
