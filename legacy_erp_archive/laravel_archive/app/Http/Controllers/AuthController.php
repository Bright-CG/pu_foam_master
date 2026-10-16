<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

class AuthController extends Controller
{
    public function showLogin()
    {
        return view('auth.login');
    }

    public function login(Request $request)
    {
        $request->validate([
            'username' => 'required|string',
            'password' => 'required|string',
        ]);

        $expectedUser = env('AUTH_ARCHIVE_USER', 'admin');
        $expectedPass = env('AUTH_ARCHIVE_PASS', 'happifoam2021');

        if ($request->username === $expectedUser && $request->password === $expectedPass) {
            $request->session()->put('archive_authenticated', true);
            $request->session()->put('archive_user', $request->username);
            return redirect()->route('dashboard');
        }

        return back()->withErrors(['credentials' => 'Invalid username or password.']);
    }

    public function logout(Request $request)
    {
        $request->session()->forget(['archive_authenticated', 'archive_user']);
        return redirect()->route('login');
    }
}
