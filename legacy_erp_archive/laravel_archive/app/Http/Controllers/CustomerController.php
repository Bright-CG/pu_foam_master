<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

class CustomerController extends Controller
{
    /**
     * Show paginated list of all customers with search.
     */
    public function index(Request $request)
    {
        $query = DB::table('customers');
        $hasStatements = Schema::hasTable('customer_statement_lines');

        if ($request->filled('search')) {
            $q = '%' . $request->search . '%';
            $query->where(function ($qb) use ($q) {
                $qb->where('id', 'like', $q)
                   ->orWhere('name', 'like', $q)
                   ->orWhere('area', 'like', $q)
                   ->orWhere('phone', 'like', $q);
            });
        }

        $customers = $query
            ->select('customers.*');

        if ($hasStatements) {
            $customers->selectSub(function ($qb) {
                $qb->from('customer_statement_lines')
                    ->selectRaw('COUNT(*)')
                    ->whereColumn('customer_statement_lines.customer_id', 'customers.id');
            }, 'statement_line_count');
        }

        $customers->selectSub(function ($qb) {
            $qb->from('customer_transactions')
                ->selectRaw('COUNT(*)')
                ->whereColumn('customer_transactions.customer_id', 'customers.id');
        }, 'inquiry_transaction_count');

        $customers = $customers
            ->orderBy('name')
            ->paginate(50)
            ->withQueryString();

        return view('customers.index', compact('customers', 'hasStatements'));
    }

    /**
     * Show a single customer's account statement.
     */
    public function show(Request $request, string $id)
    {
        $customer = DB::table('customers')->where('id', $id)->first();

        if (!$customer) {
            abort(404, 'Customer not found.');
        }

        $hasStatements = Schema::hasTable('customer_statement_lines');
        $useStatement = $hasStatements
            && DB::table('customer_statement_lines')->where('customer_id', $id)->exists();

        if ($useStatement) {
            $transQuery = DB::table('customer_statement_lines')
                ->where('customer_id', $id)
                ->orderByRaw('CAST(line_no AS INTEGER) ASC')
                ->orderBy('id', 'asc');

            if ($request->filled('from_date')) {
                $transQuery->where('trans_date', '>=', $request->from_date);
            }
            if ($request->filled('to_date')) {
                $transQuery->where('trans_date', '<=', $request->to_date);
            }
            if ($request->filled('type')) {
                $transQuery->where('trans_type', $request->type);
            }

            $transactions = $transQuery->paginate(100)->withQueryString();

            $transTypes = DB::table('customer_statement_lines')
                ->where('customer_id', $id)
                ->distinct()
                ->pluck('trans_type')
                ->filter()
                ->sort()
                ->values();

            $reportPeriod = DB::table('customer_statement_lines')
                ->where('customer_id', $id)
                ->select('report_from_date', 'report_to_date')
                ->orderByDesc('id')
                ->first();

            return view('customers.show', [
                'customer' => $customer,
                'transactions' => $transactions,
                'transTypes' => $transTypes,
                'ledgerSource' => 'statement',
                'reportPeriod' => $reportPeriod,
            ]);
        }

        $transQuery = DB::table('customer_transactions')
            ->where('customer_id', $id)
            ->orderBy('trans_date', 'asc')
            ->orderBy('trans_no', 'asc')
            ->orderBy('id', 'asc');

        if ($request->filled('from_date')) {
            $transQuery->where('trans_date', '>=', $request->from_date);
        }
        if ($request->filled('to_date')) {
            $transQuery->where('trans_date', '<=', $request->to_date);
        }
        if ($request->filled('type')) {
            $transQuery->where('trans_type', $request->type);
        }

        $transactions = $transQuery->paginate(100)->withQueryString();

        $transTypes = DB::table('customer_transactions')
            ->where('customer_id', $id)
            ->distinct()
            ->pluck('trans_type')
            ->filter()
            ->sort()
            ->values();

        return view('customers.show', [
            'customer' => $customer,
            'transactions' => $transactions,
            'transTypes' => $transTypes,
            'ledgerSource' => 'inquiry',
            'reportPeriod' => null,
        ]);
    }
}
