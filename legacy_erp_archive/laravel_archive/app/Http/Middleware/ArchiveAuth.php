<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;

class ArchiveAuth
{
    public function handle(Request $request, Closure $next)
    {
        if (!$request->session()->get('archive_authenticated')) {
            return redirect()->route('login');
        }
        return $next($request);
    }
}
