@extends('layouts.app')

@section('title', 'Chart of Accounts')

@section('content')
<div class="container-fluid p-0">
    <!-- Header -->
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <div class="d-flex align-items-center gap-2 mb-1">
                <h2 class="fw-bold text-dark mb-0">Chart of Accounts</h2>
                <span class="badge bg-secondary-subtle text-secondary border px-2 py-1">
                    {{ number_format($accounts->total()) }} Accounts
                </span>
            </div>
            <div class="text-muted small">
                Master general ledger accounts and current ledger balances
            </div>
        </div>

        <div class="d-flex align-items-center gap-2 no-print">
            <a href="{{ route('gl.trial-balance') }}" class="btn btn-emerald d-flex align-items-center gap-2 shadow-sm">
                <i class="fa-solid fa-scale-balanced"></i>
                <span>Trial Balance</span>
            </a>
            <button onclick="window.print()" class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-2">
                <i class="fa-solid fa-print"></i>
                <span>Print Chart</span>
            </button>
        </div>
    </div>

    <!-- Search & Filter Card -->
    <div class="card shadow-sm border mb-4 no-print">
        <div class="card-body p-3">
            <form action="{{ route('gl.index') }}" method="GET" class="search-form row g-2 align-items-center">
                <div class="col-12 col-md-6 col-lg-5">
                    <div class="input-group">
                        <span class="input-group-text bg-white border-end-0 text-muted">
                            <i class="fa-solid fa-magnifying-glass"></i>
                        </span>
                        <input type="text" 
                               name="search" 
                               class="form-control border-start-0 ps-0" 
                               placeholder="Search by code, account name, type, or group..." 
                               value="{{ request('search') }}">
                    </div>
                </div>

                <div class="col-auto">
                    <button type="submit" class="btn btn-emerald px-3">
                        <i class="fa-solid fa-filter me-1"></i> Filter
                    </button>
                </div>

                @if(request('search'))
                    <div class="col-auto">
                        <a href="{{ route('gl.index') }}" class="btn btn-outline-secondary px-3">
                            <i class="fa-solid fa-xmark me-1"></i> Clear
                        </a>
                    </div>
                @endif

                <div class="col text-end d-none d-md-block text-muted small">
                    Showing {{ $accounts->firstItem() ?? 0 }} to {{ $accounts->lastItem() ?? 0 }} of {{ $accounts->total() }} accounts
                </div>
            </form>
        </div>
    </div>

    <!-- Accounts Table Card -->
    <div class="card shadow-sm border">
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-striped table-hover align-middle mb-0">
                    <thead>
                        <tr>
                            <th style="width: 140px;">Account Code</th>
                            <th>Account Name</th>
                            <th style="width: 180px;">Account Type</th>
                            <th style="width: 180px;">Account Group</th>
                            <th class="text-end" style="width: 170px;">Balance</th>
                            <th class="text-center no-print" style="width: 90px;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($accounts as $acc)
                            @php
                                $bal = legacy_amount($acc->balance);
                            @endphp
                            <tr>
                                <td>
                                    <a href="{{ route('gl.show', $acc->account_code) }}" class="fw-semibold font-mono text-decoration-none text-dark">
                                        <span class="badge badge-archive font-mono">{{ $acc->account_code }}</span>
                                    </a>
                                </td>
                                <td>
                                    <a href="{{ route('gl.show', $acc->account_code) }}" class="text-decoration-none fw-semibold text-dark">
                                        {{ $acc->account_name }}
                                    </a>
                                    @if(isset($acc->section) && $acc->section)
                                        <div class="text-muted small" style="font-size: 0.78rem;">
                                            Section: {{ $acc->section }}
                                        </div>
                                    @endif
                                </td>
                                <td>
                                    <span class="badge bg-light text-secondary border font-mono">
                                        {{ $acc->account_type ?: 'General' }}
                                    </span>
                                </td>
                                <td class="small text-secondary">
                                    {{ $acc->account_group ?: '—' }}
                                </td>
                                <td class="text-end font-mono fw-bold {{ $bal > 0 ? 'text-primary' : ($bal < 0 ? 'text-danger' : 'text-muted') }}">
                                    {{ number_format($bal, 2) }}
                                </td>
                                <td class="text-center no-print">
                                    <a href="{{ route('gl.show', $acc->account_code) }}" class="btn btn-sm btn-outline-emerald py-1 px-2" title="View Account Ledger">
                                        <i class="fa-solid fa-book-open"></i>
                                    </a>
                                </td>
                            </tr>
                        @empty
                            <tr>
                                <td colspan="6" class="text-center py-5 text-muted">
                                    <i class="fa-solid fa-folder-open fs-1 d-block mb-3 text-secondary"></i>
                                    <h5>No Accounts Found</h5>
                                    <p class="small mb-0">No GL accounts match your search criteria.</p>
                                </td>
                            </tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        @if($accounts->hasPages())
            <div class="card-footer bg-white border-top p-3 d-flex flex-column flex-md-row justify-content-between align-items-center gap-2 no-print">
                <div class="text-muted small">
                    Showing {{ $accounts->firstItem() }} to {{ $accounts->lastItem() }} of {{ $accounts->total() }} accounts
                </div>
                <div>
                    {{ $accounts->links() }}
                </div>
            </div>
        @endif
    </div>
</div>
@endsection
