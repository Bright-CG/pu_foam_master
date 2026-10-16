@extends('layouts.app')

@section('title', "Customer: {$customer->id} — {$customer->name}")

@section('content')
<div class="container-fluid p-0">
    <!-- Header with Breadcrumbs & Action Buttons -->
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <div class="mb-1">
                <a href="{{ route('customers.index') }}" class="text-decoration-none text-muted small">
                    <i class="fa-solid fa-arrow-left me-1"></i> Back to Customer Accounts
                </a>
            </div>
            <div class="d-flex align-items-center gap-2 flex-wrap">
                <span class="badge badge-archive font-mono fs-6">{{ $customer->id }}</span>
                <h2 class="fw-bold text-dark mb-0">{{ $customer->name }}</h2>
                @if(($ledgerSource ?? 'inquiry') === 'statement')
                    <span class="badge bg-success-subtle text-success border">Customer Statement (ERP report)</span>
                @else
                    <span class="badge bg-light text-secondary border">Customer Inquiry (legacy scrape)</span>
                @endif
            </div>
            @if(!empty($reportPeriod?->report_from_date))
                <div class="text-muted small mt-1">
                    Statement period: <span class="font-mono">{{ $reportPeriod->report_from_date }}</span>
                    to <span class="font-mono">{{ $reportPeriod->report_to_date }}</span>
                </div>
            @endif
            <div class="text-muted small mt-1">
                @if($customer->area) <i class="fa-solid fa-location-dot me-1 text-secondary"></i>{{ $customer->area }} @endif
                @if($customer->phone) • <i class="fa-solid fa-phone me-1 text-secondary"></i>{{ $customer->phone }} @endif
                @if($customer->address) • <span>{{ $customer->address }}</span> @endif
            </div>
        </div>

        <div class="d-flex align-items-center gap-2 no-print">
            <button onclick="window.print()" class="btn btn-emerald d-flex align-items-center gap-2 shadow-sm">
                <i class="fa-solid fa-print"></i>
                <span>Print Statement</span>
            </button>
        </div>
    </div>

    <!-- Info Cards Row -->
    <div class="row g-3 mb-4">
        <!-- Account Details Card -->
        <div class="col-12 col-lg-5">
            <div class="card h-100 shadow-sm border">
                <div class="card-header bg-light py-2 px-3 fw-semibold text-secondary small text-uppercase">
                    <i class="fa-solid fa-id-card me-1 text-emerald" style="color: var(--accent-emerald);"></i> Account Profile
                </div>
                <div class="card-body p-3">
                    <div class="row g-2 small">
                        <div class="col-5 text-muted">Customer ID:</div>
                        <div class="col-7 font-mono fw-semibold text-dark">{{ $customer->id }}</div>

                        <div class="col-5 text-muted">Account Name:</div>
                        <div class="col-7 fw-semibold text-dark">{{ $customer->name }}</div>

                        <div class="col-5 text-muted">Payment Terms:</div>
                        <div class="col-7 fw-medium text-dark">{{ $customer->terms ?: 'Standard Terms' }}</div>

                        <div class="col-5 text-muted">Credit Limit:</div>
                        <div class="col-7 font-mono fw-semibold text-dark">
                            ₦ {{ format_legacy_amount($customer->credit_limit) }}
                        </div>

                        <div class="col-5 text-muted">Credit Status:</div>
                        <div class="col-7">
                            <span class="badge bg-light text-dark border">
                                {{ $customer->credit_status ?: 'Normal' }}
                            </span>
                        </div>

                        <div class="col-5 text-muted">Base Currency:</div>
                        <div class="col-7 fw-semibold text-dark">{{ $customer->currency ?: 'NGN' }}</div>

                        @if($customer->cust_type)
                            <div class="col-5 text-muted">Customer Type:</div>
                            <div class="col-7 text-dark">{{ $customer->cust_type }}</div>
                        @endif
                    </div>
                </div>
            </div>
        </div>

        <!-- Aging & Balance Breakdown Card -->
        <div class="col-12 col-lg-7">
            <div class="card h-100 shadow-sm border">
                <div class="card-header bg-light py-2 px-3 fw-semibold text-secondary small text-uppercase d-flex justify-content-between align-items-center">
                    <span><i class="fa-solid fa-chart-pie me-1 text-emerald" style="color: var(--accent-emerald);"></i> Aging &amp; Balance Breakdown</span>
                    <span class="badge bg-secondary-subtle text-secondary font-mono">Currency: {{ $customer->currency ?: 'NGN' }}</span>
                </div>
                <div class="card-body p-3">
                    <div class="row g-2 text-center">
                        <!-- Total Outstanding -->
                        <div class="col-12 mb-2 p-2 rounded bg-light border">
                            <div class="text-muted small text-uppercase fw-semibold" style="font-size: 0.75rem;">Total Outstanding Balance</div>
                            <div class="fs-3 fw-bold font-mono amount {{ legacy_amount($customer->balance_total) > 0 ? 'text-danger' : 'text-success' }}">
                                ₦ {{ format_legacy_amount($customer->balance_total) }}
                            </div>
                        </div>

                        <!-- Aging buckets -->
                        <div class="col-6 col-sm-3">
                            <div class="p-2 rounded border bg-white">
                                <div class="text-muted small" style="font-size: 0.72rem;">Current</div>
                                <div class="fw-bold font-mono text-dark small">
                                    {{ format_legacy_amount($customer->bal_current) }}
                                </div>
                            </div>
                        </div>

                        <div class="col-6 col-sm-3">
                            <div class="p-2 rounded border bg-white">
                                <div class="text-muted small" style="font-size: 0.72rem;">Now Due</div>
                                <div class="fw-bold font-mono text-dark small">
                                    {{ format_legacy_amount($customer->bal_now_due) }}
                                </div>
                            </div>
                        </div>

                        <div class="col-6 col-sm-3">
                            <div class="p-2 rounded border bg-white">
                                <div class="text-muted small" style="font-size: 0.72rem;">30-60 Days</div>
                                <div class="fw-bold font-mono text-dark small">
                                    {{ format_legacy_amount($customer->bal_30_60) }}
                                </div>
                            </div>
                        </div>

                        <div class="col-6 col-sm-3">
                            <div class="p-2 rounded border bg-white {{ legacy_amount($customer->bal_over_60) > 0 ? 'border-danger-subtle bg-danger-subtle' : '' }}">
                                <div class="text-muted small" style="font-size: 0.72rem;">Over 60 Days</div>
                                <div class="fw-bold font-mono {{ legacy_amount($customer->bal_over_60) > 0 ? 'text-danger' : 'text-dark' }} small">
                                    {{ format_legacy_amount($customer->bal_over_60) }}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Filter Bar Card -->
    <div class="card shadow-sm border mb-4 no-print">
        <div class="card-body p-3">
            <form action="{{ route('customers.show', $customer->id) }}" method="GET" class="search-form row g-2 align-items-end">
                <div class="col-12 col-sm-6 col-md-3">
                    <label class="form-label small text-muted mb-1">From Date</label>
                    <input type="date" name="from_date" class="form-control form-control-sm" value="{{ request('from_date') }}">
                </div>

                <div class="col-12 col-sm-6 col-md-3">
                    <label class="form-label small text-muted mb-1">To Date</label>
                    <input type="date" name="to_date" class="form-control form-control-sm" value="{{ request('to_date') }}">
                </div>

                <div class="col-12 col-sm-6 col-md-3">
                    <label class="form-label small text-muted mb-1">Transaction Type</label>
                    <select name="type" class="form-select form-select-sm">
                        <option value="">All Types</option>
                        @foreach($transTypes as $t)
                            <option value="{{ $t }}" {{ request('type') == $t ? 'selected' : '' }}>
                                {{ $t }}
                            </option>
                        @endforeach
                    </select>
                </div>

                <div class="col-12 col-sm-6 col-md-3 d-flex gap-2">
                    <button type="submit" class="btn btn-sm btn-emerald flex-grow-1">
                        <i class="fa-solid fa-filter me-1"></i> Filter
                    </button>
                    @if(request('from_date') || request('to_date') || request('type'))
                        <a href="{{ route('customers.show', $customer->id) }}" class="btn btn-sm btn-outline-secondary">
                            <i class="fa-solid fa-xmark me-1"></i> Clear
                        </a>
                    @endif
                </div>
            </form>
        </div>
    </div>

    <!-- Transactions Table -->
    <div class="card shadow-sm border">
        <div class="card-header bg-white py-3 d-flex justify-content-between align-items-center">
            <h5 class="fw-bold text-dark mb-0 fs-6">
                <i class="fa-solid fa-list-ol me-2 text-emerald" style="color: var(--accent-emerald);"></i> Ledger Transactions
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
                            <th style="width: 70px;">Cust ID</th>
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
                            <th style="width: 110px;">Type</th>
                            <th style="width: 90px;">Trans No</th>
                            <th style="width: 100px;">Date</th>
                            <th style="width: 90px;">Branch</th>
                            <th style="width: 110px;">Reference</th>
                            <th>Comments / Details</th>
                            <th style="width: 90px;">Order</th>
                            <th class="text-end" style="width: 120px;">Total</th>
                            <th class="text-end" style="width: 110px;">Allocated</th>
                            <th class="text-end" style="width: 120px;">Balance</th>
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
                                <td class="font-mono small">{{ $trans->customer_id ?: $customer->id }}</td>
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
                                        {{ $trans->trans_type ?: 'Unknown' }}
                                    </span>
                                </td>
                                <td class="font-mono fw-semibold text-dark">
                                    {{ $trans->trans_no }}
                                </td>
                                <td class="font-mono text-secondary small text-nowrap">
                                    {{ $trans->trans_date ? \Carbon\Carbon::parse($trans->trans_date)->format('d-M-Y') : '—' }}
                                </td>
                                <td class="small text-muted">
                                    {{ $trans->branch ?: '—' }}
                                </td>
                                <td class="font-mono small text-secondary">
                                    {{ $trans->reference ?: '—' }}
                                </td>
                                <td class="small text-dark">
                                    {{ $trans->comments ?: '—' }}
                                </td>
                                <td class="font-mono small text-muted">
                                    {{ $trans->order_no ?: '—' }}
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
                                <td colspan="10" class="text-center py-5 text-muted">
                                    <i class="fa-solid fa-receipt fs-1 d-block mb-3 text-secondary"></i>
                                    <h5>No Transactions Found</h5>
                                    <p class="small mb-0">No transaction records match the specified filters.</p>
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
