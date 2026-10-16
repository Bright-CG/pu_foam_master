@extends('layouts.app')

@section('title', "Supplier: {$supplier->id} — {$supplier->name}")

@section('content')
<div class="container-fluid p-0">
    <!-- Header with Breadcrumbs & Action Buttons -->
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <div class="mb-1">
                <a href="{{ route('suppliers.index') }}" class="text-decoration-none text-muted small">
                    <i class="fa-solid fa-arrow-left me-1"></i> Back to Supplier Accounts
                </a>
            </div>
            <div class="d-flex align-items-center gap-2">
                <span class="badge badge-archive font-mono fs-6">{{ $supplier->id }}</span>
                <h2 class="fw-bold text-dark mb-0">{{ $supplier->name }}</h2>
                @if(($ledgerSource ?? 'inquiry') === 'statement')
                    <span class="badge bg-success-subtle text-success border">Supplier Statement (ERP report)</span>
                @else
                    <span class="badge bg-light text-secondary border">Supplier Inquiry (legacy scrape)</span>
                @endif
            </div>
            @if(!empty($reportPeriod?->report_from_date))
                <div class="text-muted small mt-1">
                    Statement period: <span class="font-mono">{{ $reportPeriod->report_from_date }}</span>
                    to <span class="font-mono">{{ $reportPeriod->report_to_date }}</span>
                </div>
            @endif
            <div class="text-muted small mt-1">
                @if($supplier->phone) <i class="fa-solid fa-phone me-1 text-secondary"></i>{{ $supplier->phone }} @endif
                @if($supplier->address) • <i class="fa-solid fa-location-dot me-1 text-secondary"></i>{{ $supplier->address }} @endif
            </div>
        </div>

        <div class="d-flex align-items-center gap-2 no-print">
            <button onclick="window.print()" class="btn btn-emerald d-flex align-items-center gap-2 shadow-sm">
                <i class="fa-solid fa-print"></i>
                <span>Print Statement</span>
            </button>
        </div>
    </div>

    <!-- Info & Balance Cards Row -->
    <div class="row g-3 mb-4">
        <!-- Supplier Profile Card -->
        <div class="col-12 col-md-7">
            <div class="card h-100 shadow-sm border">
                <div class="card-header bg-light py-2 px-3 fw-semibold text-secondary small text-uppercase">
                    <i class="fa-solid fa-building me-1 text-emerald" style="color: var(--accent-emerald);"></i> Creditor Profile
                </div>
                <div class="card-body p-3">
                    <div class="row g-2 small">
                        <div class="col-4 text-muted">Supplier ID:</div>
                        <div class="col-8 font-mono fw-semibold text-dark">{{ $supplier->id }}</div>

                        <div class="col-4 text-muted">Company Name:</div>
                        <div class="col-8 fw-semibold text-dark">{{ $supplier->name }}</div>

                        <div class="col-4 text-muted">Payment Terms:</div>
                        <div class="col-8 fw-medium text-dark">{{ $supplier->terms ?: 'Standard Terms' }}</div>

                        <div class="col-4 text-muted">Currency:</div>
                        <div class="col-8 fw-semibold text-dark">{{ $supplier->currency ?: 'NGN' }}</div>

                        @if($supplier->phone)
                            <div class="col-4 text-muted">Phone:</div>
                            <div class="col-8 text-dark">{{ $supplier->phone }}</div>
                        @endif

                        @if($supplier->address)
                            <div class="col-4 text-muted">Address:</div>
                            <div class="col-8 text-dark">{{ $supplier->address }}</div>
                        @endif
                    </div>
                </div>
            </div>
        </div>

        <!-- Balance Card -->
        <div class="col-12 col-md-5">
            <div class="card h-100 shadow-sm border">
                <div class="card-header bg-light py-2 px-3 fw-semibold text-secondary small text-uppercase d-flex justify-content-between align-items-center">
                    <span><i class="fa-solid fa-wallet me-1 text-emerald" style="color: var(--accent-emerald);"></i> Account Balance</span>
                    <span class="badge bg-secondary-subtle text-secondary font-mono">{{ $supplier->currency ?: 'NGN' }}</span>
                </div>
                <div class="card-body p-3 d-flex flex-column justify-content-center text-center">
                    <div class="text-muted small text-uppercase fw-semibold mb-1">Total Outstanding Liability</div>
                    <div class="fs-2 fw-bold font-mono amount mb-2 {{ legacy_amount($supplier->balance_total) > 0 ? 'text-danger' : 'text-success' }}">
                        ₦ {{ format_legacy_amount($supplier->balance_total) }}
                    </div>
                    <div class="text-muted small">
                        Payable balance as of last archive synchronization
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Filter Bar Card -->
    <div class="card shadow-sm border mb-4 no-print">
        <div class="card-body p-3">
            <form action="{{ route('suppliers.show', $supplier->id) }}" method="GET" class="search-form row g-2 align-items-end">
                <div class="col-12 col-sm-6 col-md-4">
                    <label class="form-label small text-muted mb-1">From Date</label>
                    <input type="date" name="from_date" class="form-control form-control-sm" value="{{ request('from_date') }}">
                </div>

                <div class="col-12 col-sm-6 col-md-4">
                    <label class="form-label small text-muted mb-1">To Date</label>
                    <input type="date" name="to_date" class="form-control form-control-sm" value="{{ request('to_date') }}">
                </div>

                <div class="col-12 col-sm-12 col-md-4 d-flex gap-2">
                    <button type="submit" class="btn btn-sm btn-emerald flex-grow-1">
                        <i class="fa-solid fa-filter me-1"></i> Filter
                    </button>
                    @if(request('from_date') || request('to_date'))
                        <a href="{{ route('suppliers.show', $supplier->id) }}" class="btn btn-sm btn-outline-secondary">
                            <i class="fa-solid fa-xmark me-1"></i> Clear
                        </a>
                    @endif
                </div>
            </form>
        </div>
    </div>

    <!-- Transactions Table Card -->
    <div class="card shadow-sm border">
        <div class="card-header bg-white py-3 d-flex justify-content-between align-items-center">
            <h5 class="fw-bold text-dark mb-0 fs-6">
                <i class="fa-solid fa-list-ol me-2 text-emerald" style="color: var(--accent-emerald);"></i> Creditor Ledger Transactions
            </h5>
            <span class="badge bg-secondary-subtle text-secondary">
                {{ number_format($transactions->total()) }} entries
            </span>
        </div>
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-striped table-hover align-middle mb-0">
                    <thead>
                        @if(($ledgerSource ?? 'inquiry') === 'statement')
                        <tr>
                            <th style="width: 50px;">S/N</th>
                            <th style="width: 70px;">Supp ID</th>
                            <th style="width: 110px;">Type</th>
                            <th style="width: 90px;">Trans No.</th>
                            <th>Narration</th>
                            <th style="width: 100px;">Trans Date</th>
                            <th style="width: 110px;">Reference</th>
                            <th class="text-end" style="width: 120px;">Debit</th>
                            <th class="text-end" style="width: 120px;">Credit</th>
                            <th class="text-end" style="width: 130px;">Balances</th>
                        </tr>
                        @else
                        <tr>
                            <th style="width: 120px;">Type</th>
                            <th style="width: 100px;">Trans No</th>
                            <th style="width: 110px;">Date</th>
                            <th style="width: 120px;">Reference</th>
                            <th>Comments / Description</th>
                            <th class="text-end" style="width: 130px;">Total</th>
                            <th class="text-end" style="width: 120px;">Allocated</th>
                            <th class="text-end" style="width: 130px;">Balance</th>
                        </tr>
                        @endif
                    </thead>
                    <tbody>
                        @forelse($transactions as $trans)
                            @if(($ledgerSource ?? 'inquiry') === 'statement')
                            @php
                                $debVal = legacy_amount($trans->debit);
                                $crdVal = legacy_amount($trans->credit);
                                $balVal = legacy_amount($trans->balance);
                            @endphp
                            <tr>
                                <td class="font-mono text-muted small">{{ $trans->line_no }}</td>
                                <td class="font-mono small">{{ $trans->supplier_id ?: $supplier->id }}</td>
                                <td>
                                    <span class="badge bg-light text-dark border font-mono">
                                        {{ $trans->trans_type ?: '—' }}
                                    </span>
                                </td>
                                <td class="font-mono fw-semibold text-dark">{{ $trans->trans_no ?: '—' }}</td>
                                <td class="small text-dark">{{ $trans->narration ?: '—' }}</td>
                                <td class="font-mono text-secondary small text-nowrap">
                                    {{ $trans->trans_date ? \Carbon\Carbon::parse($trans->trans_date)->format('d-M-Y') : '—' }}
                                </td>
                                <td class="font-mono small text-secondary">{{ $trans->reference ?: '—' }}</td>
                                <td class="text-end font-mono">{{ $debVal > 0 ? format_legacy_amount($trans->debit) : '—' }}</td>
                                <td class="text-end font-mono">{{ $crdVal > 0 ? format_legacy_amount($trans->credit) : '—' }}</td>
                                <td class="text-end font-mono fw-bold {{ $balVal > 0 ? 'text-danger' : ($balVal < 0 ? 'text-success' : 'text-secondary') }}">
                                    {{ format_legacy_amount($trans->balance) }}
                                </td>
                            </tr>
                            @else
                            @php
                                $totalVal = legacy_amount($trans->total);
                                $allocVal = legacy_amount($trans->allocated);
                                $balVal = legacy_amount($trans->balance);
                            @endphp
                            <tr>
                                <td>
                                    <span class="badge bg-light text-dark border font-mono">
                                        {{ $trans->trans_type ?: 'Invoice' }}
                                    </span>
                                </td>
                                <td class="font-mono fw-semibold text-dark">
                                    {{ $trans->trans_no }}
                                </td>
                                <td class="font-mono text-secondary small text-nowrap">
                                    {{ $trans->trans_date ? \Carbon\Carbon::parse($trans->trans_date)->format('d-M-Y') : '—' }}
                                </td>
                                <td class="font-mono small text-secondary">
                                    {{ $trans->reference ?: '—' }}
                                </td>
                                <td class="small text-dark">
                                    {{ $trans->comments ?: '—' }}
                                </td>
                                <td class="text-end font-mono fw-semibold {{ $totalVal > 0 ? 'text-danger' : ($totalVal < 0 ? 'text-success' : 'text-dark') }}">
                                    {{ number_format($totalVal, 2) }}
                                </td>
                                <td class="text-end font-mono text-muted">
                                    {{ number_format($allocVal, 2) }}
                                </td>
                                <td class="text-end font-mono fw-bold {{ $balVal > 0 ? 'text-danger' : ($balVal < 0 ? 'text-success' : 'text-secondary') }}">
                                    {{ number_format($balVal, 2) }}
                                </td>
                            </tr>
                            @endif
                        @empty
                            <tr>
                                <td colspan="8" class="text-center py-5 text-muted">
                                    <i class="fa-solid fa-receipt fs-1 d-block mb-3 text-secondary"></i>
                                    <h5>No Transactions Found</h5>
                                    <p class="small mb-0">No supplier transaction records match the specified filters.</p>
                                </td>
                            </tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        @if($transactions->hasPages())
            <div class="card-footer bg-white border-top p-3 d-flex flex-column flex-md-row justify-content-between align-items-center gap-2 no-print">
                <div class="text-muted small">
                    Showing {{ $transactions->firstItem() }} to {{ $transactions->lastItem() }} of {{ $transactions->total() }} transactions
                </div>
                <div>
                    {{ $transactions->links() }}
                </div>
            </div>
        @endif
    </div>
</div>
@endsection
