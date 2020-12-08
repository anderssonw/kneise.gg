#include <iostream>
#include <string>
#include <algorithm>
#include <regex>
#include <vector>

// Has to come after <algorithm>.
#define TINS_STATIC
#include <tins/tins.h>
#include <cpr/cpr.h>
#include <nlohmann/json.hpp>

using namespace Tins;

const std::regex re_display_name("\"displayName\":\"([^\"]*)\"");
const std::regex re_connect_code("\"connectCode\":\"([^\"]*)\"");
const std::regex re_ip_address("\"oppAddress\":\"([^\"]*)\"");

std::vector<std::string> split(std::string s, std::string delimiter) {
    size_t pos_start = 0, pos_end, delim_len = delimiter.length();
    std::string token;
    std::vector<std::string> res;

    while ((pos_end = s.find(delimiter, pos_start)) != std::string::npos)
    {
        token = s.substr(pos_start, pos_end - pos_start);
        pos_start = pos_end + delim_len;
        res.push_back(token);
    }

    res.push_back(s.substr(pos_start));
    return res;
}

std::string geolocate_ip_address(std::string &ip_address)
{
    cpr::Response r = cpr::Get(cpr::Url{"https://freegeoip.app/csv/" + ip_address});
    std::vector<std::string> ip_info = split(std::string(r.text), ",");
    return ip_info[5] + ", " + ip_info[4] + ", " + ip_info[2];
}

void post_whomst(std::string display_name, std::string connect_code,
                 std::string ip_address, std::string region)
{
    nlohmann::json json =
    {
      {"display_name", display_name},
      {"connect_code", connect_code},
      {"ip_address", ip_address},
      {"region", region},
    };

    cpr::Response r = cpr::Post(cpr::Url{"https://kneise.eu/whomst/insert"},
                                cpr::Body{json.dump()},
                                cpr::Header{{"content-type", "application/json"}});
}

bool sniff_callback(const PDU &pdu)
{
    const IP &ip = pdu.rfind_pdu<IP>(); 
    const UDP &udp = pdu.rfind_pdu<UDP>();

    const RawPDU &raw = udp.rfind_pdu<RawPDU>();
    const RawPDU::payload_type &payload = raw.payload();
    const std::string payload_str(payload.begin(), payload.end());

    if (payload_str.find("get-ticket-resp") != std::string::npos)
    {
        std::smatch display_name_match;
        std::smatch connect_code_match;
        std::smatch ip_address_match;

        std::regex_search(payload_str, display_name_match, re_display_name);
        std::regex_search(payload_str, connect_code_match, re_connect_code);
        std::regex_search(payload_str, ip_address_match, re_ip_address);

        std::string display_name = display_name_match[1];
        std::string connect_code = connect_code_match[1];
        std::string ip_address = ip_address_match[1];

        std::string::size_type port_pos = ip_address.find(':');
        ip_address = ip_address.substr(0, port_pos);
        std::string region = geolocate_ip_address(ip_address);

        std::cout << "Opponent:" << std::endl;
        std::cout << "  Display name:  " << display_name << std::endl;
        std::cout << "  Connect code:  " << connect_code << std::endl;
        std::cout << "  IP-address:    " << ip_address << std::endl;
        std::cout << "  Region:        " << region << std::endl;

        post_whomst(display_name, connect_code, ip_address, region);
    }

    return true;
}

int main(int argc, char *argv[])
{
    const NetworkInterface &default_interface = NetworkInterface::default_interface();

    SnifferConfiguration sniffer_config;
    sniffer_config.set_filter("udp and not ip broadcast and not ip multicast");
    sniffer_config.set_promisc_mode(true);
    sniffer_config.set_immediate_mode(true);

    std::cout << "Waiting for Slippi match..." << std::endl;
    try
    {
        Sniffer sniffer(default_interface.name(), sniffer_config);
        sniffer.sniff_loop(sniff_callback);
    }
    catch (const std::exception &e)
    {
        std::cout << e.what() << std::endl;
    }
}
