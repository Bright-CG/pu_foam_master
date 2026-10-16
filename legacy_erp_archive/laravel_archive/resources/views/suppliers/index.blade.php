@extends('layouts.app')

@section('title', 'Supplier Accounts')

@section('content')
<div class="container-fluid p-0">
    <!-- Header -->
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <div class="d-flex align-items-center gap-2 mb-1">
                <h2 class="fw-bold text-dark mb-0">Supplier Accounts</h2>
                <span class="badge bg-secondary-subtle text-secondary border px-2 py-1">
                    {{ number_format($suppliers->total()) }} Total
                </span>
            </div>
            <div class="text-muted small">
                Supplier statements (debit / credit / balance)
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
            <form action="{{ route('suppliers.index') }}" method="GET" class="search-form row g-2 align-items-center">
                <div class="col-12 col-md-6 col-lg-5">
                    <div class="input-group">
                        <span class="input-group-text bg-white border-end-0 text-muted">
                            <i class="fa-solid fa-magnifying-glass"></i>
                        </span>
                        <input type="text" 
                               name="search" 
                               class="form-control border-start-0 ps-0" 
                               placeholder="Search by ID, supplier name, or phone..." 
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
                        <a href="{{ route('suppliers.index') }}" class="btn btn-outline-secondary px-3">
                            <i class="fa-solid fa-xmark me-1"></i> Clear
                        </a>
                    </div>
                @endif

                <div class="col text-end d-none d-md-block text-muted small">
                    Showing {{ $suppliers->firstItem() ?? 0 }} to {{ $suppliers->lastItem() ?? 0 }} of {{ $suppliers->total() }} records
                </div>
            </form>
        </div>
    </div>

    <!-- Suppliers Table Card -->
    <div class="card shadow-sm border">
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-striped table-hover align-middle mb-0">
                    <thead>
                        <tr>
                            <th style="width: 120px;">Supplier ID</th>
                            <th>Supplier Name</th>
                            <th>Contact / Phone</th>
                            <th style="width: 140px;">Terms</th>
                            <th class="text-end" style="width: 160px;">Total Balance</th>
                            <th class="text-end" style="width: 110px;">Transactions</th>
                            <th class="text-center no-print" style="width: 90px;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($suppliers as $supplier)
                            @php
                                $balTotal = legacy_amount($supplier->balance_total);
                            @endphp
                            <tr class="{{ $balTotal > 0.009 ? 'row-has-balance' : '' }}">
                                <td>
                                    <a href="{{ route('suppliers.show', $supplier->id) }}" class="fw-semibold font-mono text-decoration-none text-dark">
                                        <span class="badge badge-archive">{{ $supplier->id }}</span>
                                    </a>
                                </td>
                                <td>
                                    <div class="fw-semibold text-dark">
                                        <a href="{{ route('suppliers.show', $supplier->id) }}" class="text-decoration-none text-dark">
                                            {{ $supplier->name }}
                                        </a>
                                    </div>
                                    @if($supplier->address)
                                        <div class="text-muted small" style="font-size: 0.78rem;">
                                            <i class="fa-solid fa-location-dot me-1 text-secondary"></i>{{ $supplier->address }}
                                        </div>
                                    @endif
                                </td>
                                <td class="small text-muted">
                                    {{ $supplier->phone ?: '—' }}
                                </td>
                                <td class="small text-secondary">
                                    {{ $supplier->terms ?: 'Standard Terms' }}
                                </td>
                                <td class="text-end font-mono fw-bold {{ $balTotal > 0 ? 'text-danger' : ($balTotal < 0 ? 'text-success' : 'text-muted') }}">
                                    {{ number_format($balTotal, 2) }}
                                </td>
                                <td class="text-end font-mono text-secondary">
                                    {{ number_format((int) ($supplier->transaction_count ?? 0)) }}
                                </td>
                                <td class="text-center no-print">
                                    <a href="{{ route('suppliers.show', $supplier->id) }}" class="btn btn-sm btn-outline-emerald py-1 px-2" title="View Ledger">
                                        <i class="fa-solid fa-file-invoice"></i>
                                    </a>
                                </td>
                            </tr>
                        @empty
                            <tr>
                                <td colspan="7" class="text-center py-5 text-muted">
                                    <i class="fa-solid fa-truck-ramp-box fs-1 d-block mb-3 text-secondary"></i>
                                    <h5>No Supplier Accounts Found</h5>
                                    <p class="small mb-0">No records match your search criteria. Try modifying your search query.</p>
                                </td>
                            </tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        @if($suppliers->hasPages())
            <div class="card-footer bg-white border-top p-3 d-flex flex-column flex-md-row justify-content-between align-items-center gap-2 no-print">
                <div class="text-muted small">
                    Showing {{ $suppliers->firstItem() }} to {{ $suppliers->lastItem() }} of {{ $suppliers->total() }} suppliers
                </div>
                <div>
                    {{ $suppliers->links() }}
                </div>
            </div>
        @endif
    </div>
</div>
@endsection
