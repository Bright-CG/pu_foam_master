@extends('layouts.app')

@section('title', 'Customer Accounts')

@section('content')
<div class="container-fluid p-0">
    <!-- Header -->
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <div class="d-flex align-items-center gap-2 mb-1">
                <h2 class="fw-bold text-dark mb-0">Customer Accounts</h2>
                <span class="badge bg-secondary-subtle text-secondary border px-2 py-1">
                    {{ number_format($customers->total()) }} Total
                </span>
            </div>
            <div class="text-muted small">
                Customer statements (debit / credit / balance)
            </div>
        </div>

        <div class="d-flex align-items-center gap-2 no-print">
            <button onclick="window.print()" class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-2">
                <i class="fa-solid fa-print"></i>
                <span>Print List</span>
            </button>
        </div>
    </div>

    <!-- Search & Filter Card -->
    <div class="card shadow-sm border mb-4 no-print">
        <div class="card-body p-3">
            <form action="{{ route('customers.index') }}" method="GET" class="search-form row g-2 align-items-center">
                <div class="col-12 col-md-6 col-lg-5">
                    <div class="input-group">
                        <span class="input-group-text bg-white border-end-0 text-muted">
                            <i class="fa-solid fa-magnifying-glass"></i>
                        </span>
                        <input type="text" 
                               name="search" 
                               class="form-control border-start-0 ps-0" 
                               placeholder="Search by ID, name, area, or phone..." 
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
                        <a href="{{ route('customers.index') }}" class="btn btn-outline-secondary px-3">
                            <i class="fa-solid fa-xmark me-1"></i> Clear
                        </a>
                    </div>
                @endif

                <div class="col text-end d-none d-md-block text-muted small">
                    Showing {{ $customers->firstItem() ?? 0 }} to {{ $customers->lastItem() ?? 0 }} of {{ $customers->total() }} records
                </div>
            </form>
        </div>
    </div>

    <!-- Customers Table Card -->
    <div class="card shadow-sm border">
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-striped table-hover align-middle mb-0">
                    <thead>
                        <tr>
                            <th style="width: 100px;">Customer ID</th>
                            <th>Customer Name</th>
                            <th class="text-end" style="width: 130px;">Total Balance</th>
                            <th class="text-end" style="width: 120px;">Current</th>
                            <th class="text-end" style="width: 120px;">Now Due</th>
                            <th class="text-end" style="width: 120px;">30-60 Days</th>
                            <th class="text-end" style="width: 120px;">Over 60 Days</th>
                            <th class="text-end" style="width: 110px;">Transactions</th>
                            <th class="text-center no-print" style="width: 90px;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($customers as $customer)
                            @php
                                $balTotal = legacy_amount($customer->balance_total);
                                $hasBalance = $balTotal > 0.009 || $balTotal < -0.009;
                            @endphp
                            <tr class="{{ $balTotal > 0.009 ? 'row-has-balance' : '' }}">
                                <td>
                                    <a href="{{ route('customers.show', $customer->id) }}" class="fw-semibold font-mono text-decoration-none text-dark">
                                        <span class="badge badge-archive">{{ $customer->id }}</span>
                                    </a>
                                </td>
                                <td>
                                    <div class="fw-semibold text-dark">
                                        <a href="{{ route('customers.show', $customer->id) }}" class="text-decoration-none text-dark">
                                            {{ $customer->name }}
                                        </a>
                                    </div>
                                    @if($customer->area || $customer->phone)
                                        <div class="text-muted small" style="font-size: 0.78rem;">
                                            @if($customer->area)<i class="fa-solid fa-location-dot me-1 text-secondary"></i>{{ $customer->area }}@endif
                                            @if($customer->area && $customer->phone) • @endif
                                            @if($customer->phone)<i class="fa-solid fa-phone me-1 text-secondary"></i>{{ $customer->phone }}@endif
                                        </div>
                                    @endif
                                </td>
                                <td class="text-end font-mono fw-bold {{ $balTotal > 0 ? 'text-danger' : ($balTotal < 0 ? 'text-success' : 'text-muted') }}">
                                    {{ number_format($balTotal, 2) }}
                                </td>
                                <td class="text-end font-mono text-secondary">
                                    {{ format_legacy_amount($customer->bal_current) }}
                                </td>
                                <td class="text-end font-mono text-secondary">
                                    {{ format_legacy_amount($customer->bal_now_due) }}
                                </td>
                                <td class="text-end font-mono text-secondary">
                                    {{ format_legacy_amount($customer->bal_30_60) }}
                                </td>
                                <td class="text-end font-mono {{ legacy_amount($customer->bal_over_60) > 0 ? 'text-danger fw-semibold' : 'text-secondary' }}">
                                    {{ format_legacy_amount($customer->bal_over_60) }}
                                </td>
                                <td class="text-end font-mono text-secondary">
                                    @php
                                        $stmtCnt = (int) ($customer->statement_line_count ?? 0);
                                        $inqCnt = (int) ($customer->inquiry_transaction_count ?? 0);
                                        $lineCnt = $stmtCnt > 0 ? $stmtCnt : $inqCnt;
                                    @endphp
                                    {{ number_format($lineCnt) }}
                                    @if($stmtCnt > 0)
                                        <span class="d-block text-success" style="font-size:0.65rem;">statement</span>
                                    @endif
                                </td>
                                <td class="text-center no-print">
                                    <a href="{{ route('customers.show', $customer->id) }}" class="btn btn-sm btn-outline-emerald py-1 px-2" title="View Statement">
                                        <i class="fa-solid fa-file-invoice"></i>
                                    </a>
                                </td>
                            </tr>
                        @empty
                            <tr>
                                <td colspan="8" class="text-center py-5 text-muted">
                                    <i class="fa-solid fa-users-slash fs-1 d-block mb-3 text-secondary"></i>
                                    <h5>No Customer Accounts Found</h5>
                                    <p class="small mb-0">No records match your search criteria. Try modifying your search query.</p>
                                </td>
                            </tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        @if($customers->hasPages())
            <div class="card-footer bg-white border-top p-3 d-flex flex-column flex-md-row justify-content-between align-items-center gap-2 no-print">
                <div class="text-muted small">
                    Showing {{ $customers->firstItem() }} to {{ $customers->lastItem() }} of {{ $customers->total() }} customers
                </div>
                <div>
                    {{ $customers->links() }}
                </div>
            </div>
        @endif
    </div>
</div>
@endsection
