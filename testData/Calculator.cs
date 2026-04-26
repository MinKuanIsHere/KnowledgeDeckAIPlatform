using System;
using System.Collections.Generic;

namespace KnowledgeDeck.Sample.Math;

/// <summary>
/// Stack-based RPN calculator with a small operator set. Designed as a
/// teaching example for unit testing — every public method is pure and
/// deterministic, no IO, no time, no randomness.
/// </summary>
public class Calculator
{
    private readonly Stack<double> _stack = new();

    public double? Top => _stack.Count == 0 ? null : _stack.Peek();
    public int Depth => _stack.Count;

    public void Push(double value)
    {
        if (double.IsNaN(value)) throw new ArgumentException("NaN not permitted");
        if (double.IsInfinity(value)) throw new ArgumentException("infinity not permitted");
        _stack.Push(value);
    }

    public double Pop()
    {
        if (_stack.Count == 0) throw new InvalidOperationException("stack is empty");
        return _stack.Pop();
    }

    public void Clear() => _stack.Clear();

    public void Apply(string op)
    {
        switch (op)
        {
            case "+":
                BinaryOp((a, b) => a + b);
                break;
            case "-":
                BinaryOp((a, b) => a - b);
                break;
            case "*":
                BinaryOp((a, b) => a * b);
                break;
            case "/":
                BinaryOp((a, b) =>
                {
                    if (b == 0) throw new DivideByZeroException();
                    return a / b;
                });
                break;
            case "neg":
                UnaryOp(a => -a);
                break;
            case "abs":
                UnaryOp(System.Math.Abs);
                break;
            case "sqrt":
                UnaryOp(a =>
                {
                    if (a < 0) throw new ArgumentException("sqrt of negative");
                    return System.Math.Sqrt(a);
                });
                break;
            default:
                throw new ArgumentException($"unknown operator: {op}");
        }
    }

    /// <summary>
    /// Evaluates a whitespace-separated RPN expression and returns the
    /// final stack top. Convenience for the test fixtures.
    /// </summary>
    public double Eval(string expression)
    {
        Clear();
        foreach (var token in expression.Split(' ', StringSplitOptions.RemoveEmptyEntries))
        {
            if (double.TryParse(token, out var value))
            {
                Push(value);
            }
            else
            {
                Apply(token);
            }
        }
        if (_stack.Count != 1)
            throw new InvalidOperationException(
                $"expression did not reduce to a single value (depth={_stack.Count})");
        return _stack.Peek();
    }

    private void BinaryOp(Func<double, double, double> op)
    {
        if (_stack.Count < 2)
            throw new InvalidOperationException("binary op requires two operands");
        var b = _stack.Pop();
        var a = _stack.Pop();
        _stack.Push(op(a, b));
    }

    private void UnaryOp(Func<double, double> op)
    {
        if (_stack.Count < 1)
            throw new InvalidOperationException("unary op requires one operand");
        var a = _stack.Pop();
        _stack.Push(op(a));
    }
}
