#include <filesystem>
#include <string>
#include <iostream>
#include <exception>

#include <tchar.h>
#include <windows.h>
#include <detours/detours.h>

#pragma comment(lib, "detours.lib")

void stdout_last_error()
{
	DWORD error = GetLastError();

	LPSTR msg_buf = nullptr;
	size_t size = FormatMessageA(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
		nullptr, error, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT), (LPSTR)&msg_buf, 0, nullptr);
	{
		std::string msg(msg_buf, size);
		std::cout << msg << std::endl;
	}
	LocalFree(msg_buf);
}

int main(int argc, char *argv[])
{
	try
	{
		std::wstring wdir = std::filesystem::current_path().wstring();
		std::wstring dolphin = wdir + std::wstring{ L"\\Dolphin.exe" };

		std::string ldir = std::filesystem::current_path().string();
		std::string dll = ldir + std::string{ "\\whomst.dll" };

		STARTUPINFO si;
		PROCESS_INFORMATION pi;
		ZeroMemory(&si, sizeof(si));
		ZeroMemory(&pi, sizeof(pi));
		si.cb = sizeof(si);
		si.dwFlags = STARTF_USESHOWWINDOW;
		si.wShowWindow = SW_SHOW;

		if (not DetourCreateProcessWithDll(&dolphin[0], nullptr, nullptr, nullptr,
			true, CREATE_DEFAULT_ERROR_MODE | CREATE_SUSPENDED, nullptr, &wdir[0], &si, &pi, &dll[0], nullptr))
		{
			std::cout << "DetourCreateProcessWithDll failed:" << std::endl;
			std::cout << "  "; stdout_last_error();
			ExitProcess(9009);
		}

		ResumeThread(pi.hThread);
		WaitForSingleObject(pi.hProcess, INFINITE);
		CloseHandle(&si);
		CloseHandle(&pi);
	}
	catch (std::exception & e)
	{
		std::cout << e.what() << std::endl;
	}
}