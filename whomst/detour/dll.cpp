#define _SILENCE_CXX17_C_HEADER_DEPRECATION_WARNING 1
#define _SILENCE_ALL_CXX17_DEPRECATION_WARNINGS 1

#include <iostream>
#include <regex>
#include <vector>
#include <ctime>

#include <tchar.h>
#include <winsock2.h>
#include <windows.h>
#include <detours/detours.h>
#include <cpr/cpr.h>
#include <nlohmann/json.hpp>

#pragma comment(lib, "detours.lib")
#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "mswsock.lib")
#pragma comment (lib, "crypt32.lib")
#pragma comment (lib, "wldap32.lib")

#define UNUSED(v) ((void)(v))

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

std::string geolocate_ip_address(std::string& ip_address)
{
	cpr::Response r = cpr::Get(cpr::Url{ "https://freegeoip.app/csv/" + ip_address });
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

	cpr::Response r = cpr::Post(cpr::Url{ "https://kneise.eu/whomst/insert" },
		cpr::Body{ json.dump() },
		cpr::Header{ {"content-type", "application/json"} });
}

std::clock_t prev_recv{};

void handle_packet(std::string &packet)
{
	if (packet.find("get-ticket-resp") != std::string::npos)
	{
		std::clock_t now = clock();
		double elapsed_s = double(now - prev_recv) / CLOCKS_PER_SEC;
		if (elapsed_s < 2.0) return;
		prev_recv = now;

		std::smatch display_name_match;
		std::smatch connect_code_match;
		std::smatch ip_address_match;

		std::regex_search(packet, display_name_match, re_display_name);
		std::regex_search(packet, connect_code_match, re_connect_code);
		std::regex_search(packet, ip_address_match, re_ip_address);

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
 }

struct enet_buffer
{
	size_t len;
	void* data;
};

int (WINAPI* real_wsarecvfrom)(SOCKET s, LPWSABUF lpBuffers, DWORD dwBufferCount, LPDWORD lpNumberOfBytesRecvd,
	LPDWORD lpFlags, sockaddr* lpFrom, LPINT lpFromlen, LPWSAOVERLAPPED lpOverlapped,
	LPWSAOVERLAPPED_COMPLETION_ROUTINE lpCompletionRoutine) = WSARecvFrom;

int WINAPI fake_wsarecvfrom(SOCKET s, LPWSABUF lpBuffers, DWORD dwBufferCount, LPDWORD lpNumberOfBytesRecvd,
	LPDWORD lpFlags, sockaddr* lpFrom, LPINT lpFromlen, LPWSAOVERLAPPED lpOverlapped,
	LPWSAOVERLAPPED_COMPLETION_ROUTINE lpCompletionRoutine)
{
	int err =  real_wsarecvfrom(s, lpBuffers, dwBufferCount, lpNumberOfBytesRecvd, lpFlags, lpFrom, 
		lpFromlen, lpOverlapped, lpCompletionRoutine);
	{
		enet_buffer* buffers = reinterpret_cast<enet_buffer*>(lpBuffers);
		int buffer_count = static_cast<int>(dwBufferCount);
		for (int i = 0; i < buffer_count; ++i)
		{
			std::string packet{};
			packet.assign(reinterpret_cast<char*>(buffers[i].data), buffers[i].len);
			handle_packet(packet);
		}
	}
	return err;
}

void attach_console()
{
	if (!AttachConsole(-1)) {
		return;
	}

	FILE* dummy;
	freopen_s(&dummy, "CONOUT$", "w", stdout);
	freopen_s(&dummy, "CONOUT$", "w", stderr);
	freopen_s(&dummy, "CONIN$", "r", stdin);

	std::cout.clear();
	std::clog.clear();
	std::cerr.clear();
	std::cin.clear();

	HANDLE hConOut = CreateFile(_T("CONOUT$"), GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
	HANDLE hConIn = CreateFile(_T("CONIN$"), GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
	SetStdHandle(STD_OUTPUT_HANDLE, hConOut);
	SetStdHandle(STD_ERROR_HANDLE, hConOut);
	SetStdHandle(STD_INPUT_HANDLE, hConIn);

	std::wcout.clear();
	std::wclog.clear();
	std::wcerr.clear();
	std::wcin.clear();
}

void err_out(LONG error)
{
	if (error != NO_ERROR)
	{
		std::cout << DETOURS_STRINGIFY(DETOURS_BITS) << ".dll:\n  " << error << std::endl;
	}
}

extern "C" __declspec(dllexport) void dummy(void) {
	return;
}

BOOL WINAPI DllMain(HINSTANCE hinst, DWORD dwReason, LPVOID reserved)
{
	LONG error;
	UNUSED(hinst);
	UNUSED(reserved);

	attach_console();
	prev_recv = clock();

	if (DetourIsHelperProcess())
	{
		return TRUE;
	}

	if (dwReason == DLL_PROCESS_ATTACH)
	{
		DetourRestoreAfterWith();

		DetourTransactionBegin();
		DetourUpdateThread(GetCurrentThread());
		DetourAttach(&(PVOID&)real_wsarecvfrom, fake_wsarecvfrom);
		error = DetourTransactionCommit();

		err_out(error);
	}
	else if (dwReason == DLL_PROCESS_DETACH)
	{
		DetourTransactionBegin();
		DetourUpdateThread(GetCurrentThread());
		DetourDetach(&(PVOID&)real_wsarecvfrom, fake_wsarecvfrom);
		error = DetourTransactionCommit();

		err_out(error);
	}

	return TRUE;
}