<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\CustomerController;
use App\Http\Controllers\SupplierController;
use App\Http\Controllers\GeneralLedgerController;
use App\Http\Controllers\InventoryController;

// ── Public routes ──────────────────────────────────────────────────────────
Route::get('/login', [AuthController::class, 'showLogin'])->name('login');
Route::post('/login', [AuthController::class, 'login'])->name('login.submit');
Route::post('/logout', [AuthController::class, 'logout'])->name('logout');

// ── Protected routes (require ArchiveAuth middleware) ─────────────────────
Route::middleware(['web', \App\Http\Middleware\ArchiveAuth::class])->group(function () {

    // Dashboard
    Route::get('/', [DashboardController::class, 'index'])->name('dashboard');

    // Customer Ledger
    Route::get('/customers', [CustomerController::class, 'index'])->name('customers.index');
    Route::get('/customers/{id}', [CustomerController::class, 'show'])->name('customers.show');

    // Supplier Ledger
    Route::get('/suppliers', [SupplierController::class, 'index'])->name('suppliers.index');
    Route::get('/suppliers/{id}', [SupplierController::class, 'show'])->name('suppliers.show');

    // General Ledger
    Route::get('/gl', [GeneralLedgerController::class, 'index'])->name('gl.index');
    Route::get('/gl/trial-balance', [GeneralLedgerController::class, 'trialBalance'])->name('gl.trial-balance');
    Route::get('/gl/{code}', [GeneralLedgerController::class, 'show'])->name('gl.show');

    // Inventory
    Route::get('/inventory', [InventoryController::class, 'index'])->name('inventory.index');
});
