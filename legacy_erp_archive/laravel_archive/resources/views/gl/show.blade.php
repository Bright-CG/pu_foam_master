@extends('layouts.app')

@section('title', "GL Account: {$account->account_code} — {$account->account_name}")

@section('content')
<div class="container-fluid p-0">
    <!-- Header with Breadcrumbs & Action Buttons -->
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <div class="mb-1">
                <a href="{{ route('gl.index') }}" class="text-decoration-none text-muted small">
                    <i class="fa-solid fa-arrow-left me-1"></i> Back to Chart of Accounts
                </a>
            </div>
            <div class="d-flex align-items-center gap-2 flex-wrap">
                <span class="badge badge-archive font-mono fs-6">{{ $account->account_code }}</span>
                <h2 class="fw-bold text-dark mb-0">{{ $account->account_name }}</h2>
                @if(($ledgerSource ?? 'journal') === 'inquiry')
                    <span class="badge bg-success-subtle text-success border">GL Account Inquiry (ERP)</span>
                @else
                    <span class="badge bg-light text-secondary border">Journal inquiry (legacy scrape)</span>
                @endif
            </div>
            <div class="text-muted small mt-1">
                Type: <span class="fw-semibold text-dark">{{ $account->account_type ?: 'General' }}</span>
                @if($account->account_group) • Group: <span class="fw-medium text-dark">{{ $account->account_group }}</span> @endif
                @if(isset($account->section) && $account->section) • Section: <span class="fw-medium text-dark">{{ $account->section }}</span> @endif
            </div>
        </div>

        <div class="d-flex align-items-center gap-2 no-print">
            <button onclick="window.print()" class="btn btn-emerald d-flex align-items-center gap-2 shadow-sm">
                <i class="fa-solid fa-print"></i>
                <span>Print Ledger</span>
            </button>
        </div>
    </div>

    <!-- Summary & Balance Cards Row -->
    <div class="row g-3 mb-4">
        <!-- Account Summary -->
        <div class="col-12 col-md-7">
            <div class="card h-100 shadow-sm border">
                <div class="card-header bg-light py-2 px-3 fw-semibold text-secondary small text-uppercase">
                    <i class="fa-solid fa-circle-info me-1 text-emerald" style="color: var(--accent-emerald);"></i> Account Specifications
                </div>
                <div class="card-body p-3">
                    <div class="row g-2 small">
                        <div class="col-4 text-muted">Account Code:</div>
                        <div class="col-8 font-mono fw-semibold text-dark">{{ $account->account_code }}</div>

                        <div class="col-4 text-muted">Account Name:</div>
                        <div class="col-8 fw-semibold text-dark">{{ $account->account_name }}</div>

                        <div class="col-4 text-muted">Account Type:</div>
                        <div class="col-8">
                            <span class="badge bg-light text-secondary border font-mono">
                                {{ $account->account_type ?: 'General' }}
                            </span>
                        </div>

                        <div class="col-4 text-muted">Account Group:</div>
                        <div class="col-8 fw-medium text-dark">{{ $account->account_group ?: '—' }}</div>

                        @if(isset($account->section) && $account->section)
                            <div class="col-4 text-muted">Reporting Section:</div>
                            <div class="col-8 text-dark">{{ $account->section }}</div>
                        @endif
                    </div>
                </div>
            </div>
        </div>

        <!-- Ledger Balance Card -->
        <div class="col-12 col-md-5">
            <div class="card h-100 shadow-sm border">
                <div class="card-header bg-light py-2 px-3 fw-semibold text-secondary small text-uppercase d-flex justify-content-between align-items-center">
                    <span><i class="fa-solid fa-scale-balanced me-1 text-emerald" style="color: var(--accent-emerald);"></i> Current Ledger Balance</span>
                    <span class="badge bg-secondary-subtle text-secondary font-mono">NGN</span>
                </div>
                <div class="card-body p-3 d-flex flex-column justify-content-center text-center">
                    <div class="text-muted small text-uppercase fw-semibold mb-1">Net Balance</div>
                    @php $bal = legacy_amount($account->balance); @endphp
                    <div class="fs-2 fw-bold font-mono amount mb-2 {{ $bal > 0 ? 'text-primary' : ($bal < 0 ? 'text-danger' : 'text-dark') }}">
                        ₦ {{ number_format($bal, 2) }}
                    </div>
                    <div class="text-muted small">
                        Cumulative balance across all journal movements
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Filter Bar Card -->
    <div class="card shadow-sm border mb-4 no-print">
        <div class="card-body p-3">
            <form action="{{ route('gl.show', $account->account_code) }}" method="GET" class="search-form row g-2 align-items-end">
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
                        <a href="{{ route('gl.show', $account->account_code) }}" class="btn btn-sm btn-outline-secondary">
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
                <i class="fa-solid fa-list-check me-2 text-emerald" style="color: var(--accent-emerald);"></i>
                {{ ($ledgerSource ?? 'journal') === 'inquiry' ? 'Account Transactions' : 'General Journal Entries' }}
            </h5>
            <span class="badge bg-secondary-subtle text-secondary">
                {{ number_format($transactions->total()) }} entries
            </span>
        </div>
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-striped table-hover align-middle mb-0">
                    <thead>
                        <tr>
                            <th style="width: 110px;">Type</th>
                            <th style="width: 90px;">Number</th>
                            <th style="width: 100px;">Date</th>
                            <th>Narrative</th>
                            <th class="text-end" style="width: 130px;">Debit</th>
                            <th class="text-end" style="width: 130px;">Credit</th>
                            <th class="text-end" style="width: 140px;">Balance</th>
                            @if(($ledgerSource ?? 'journal') === 'inquiry')
                            <th style="width: 100px;">Tag</th>
                            @endif
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($transactions as $trans)
                            @php
                                $debVal = legacy_amount($trans->debit);
                                $crdVal = legacy_amount($trans->credit);
                                $balVal = legacy_amount($trans->balance);
                            @endphp
                            <tr>
                                <td>
                                    <span class="badge bg-light text-dark border font-mono small">
                                        {{ $trans->trans_type ?: 'GL' }}
                                    </span>
                                </td>
                                <td class="font-mono fw-semibold text-dark">
                                    {{ $trans->trans_no ?: '—' }}
                                </td>
                                <td class="font-mono text-secondary small text-nowrap">
                                    {{ $trans->trans_date ? \Carbon\Carbon::parse($trans->trans_date)->format('d-M-Y') : '—' }}
                                </td>
                                <td class="small text-dark">
                                    {{ $trans->narrative ?: '—' }}
                                </td>
                                <td class="text-end font-mono {{ $debVal > 0 ? 'fw-semibold text-dark' : 'text-muted' }}">
                                    {{ $debVal > 0 ? format_legacy_amount($trans->debit) : '—' }}
                                </td>
                                <td class="text-end font-mono {{ $crdVal > 0 ? 'fw-semibold text-dark' : 'text-muted' }}">
                                    {{ $crdVal > 0 ? format_legacy_amount($trans->credit) : '—' }}
                                </td>
                                <td class="text-end font-mono fw-bold {{ $balVal > 0 ? 'text-primary' : ($balVal < 0 ? 'text-danger' : 'text-secondary') }}">
                                    {{ format_legacy_amount($trans->balance) }}
                                </td>
                                @if(($ledgerSource ?? 'journal') === 'inquiry')
                                <td class="small text-muted">{{ $trans->tag ?? '—' }}</td>
                                @endif
                            </tr>
                        @empty
                            <tr>
                                <td colspan="{{ ($ledgerSource ?? 'journal') === 'inquiry' ? 8 : 7 }}" class="text-center py-5 text-muted">
                                    <i class="fa-solid fa-book-open fs-1 d-block mb-3 text-secondary"></i>
                                    <h5>No Journal Entries Found</h5>
                                    <p class="small mb-0">No movements found matching the specified date parameters.</p>
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
                    Showing {{ $transactions->firstItem() }} to {{ $transactions->lastItem() }} of {{ $transactions->total() }} entries
                </div>
                <div>
                    {{ $transactions->links() }}
                </div>
            </div>
        @endif
    </div>
</div>
@endsection
