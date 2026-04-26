using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace KnowledgeDeck.Sample.Orders;

/// <summary>
/// Domain service that coordinates order placement, inventory checks,
/// and payment authorization. Persistence is delegated to repositories
/// so the service stays testable without a real database.
/// </summary>
public class OrderService
{
    private readonly IOrderRepository _orders;
    private readonly IInventoryClient _inventory;
    private readonly IPaymentGateway _payments;
    private readonly ILogger<OrderService> _logger;

    public OrderService(
        IOrderRepository orders,
        IInventoryClient inventory,
        IPaymentGateway payments,
        ILogger<OrderService> logger)
    {
        _orders = orders;
        _inventory = inventory;
        _payments = payments;
        _logger = logger;
    }

    public async Task<PlaceOrderResult> PlaceOrderAsync(PlaceOrderRequest request)
    {
        if (request is null) throw new ArgumentNullException(nameof(request));
        if (!request.Items.Any())
            return PlaceOrderResult.Rejected("order must contain at least one line item");

        var reservation = await _inventory.ReserveAsync(request.Items);
        if (!reservation.Succeeded)
        {
            _logger.LogWarning(
                "inventory_reservation_failed customer={Customer} reason={Reason}",
                request.CustomerId, reservation.FailureReason);
            return PlaceOrderResult.Rejected(reservation.FailureReason);
        }

        var charge = await _payments.AuthorizeAsync(
            request.CustomerId, reservation.TotalCents);
        if (!charge.Authorized)
        {
            // Roll the inventory back so the units are not held forever.
            await _inventory.ReleaseAsync(reservation.ReservationId);
            return PlaceOrderResult.Rejected(charge.DeclineReason ?? "payment_declined");
        }

        var order = new Order(
            customerId: request.CustomerId,
            items: request.Items.ToList(),
            paymentToken: charge.PaymentToken,
            reservationId: reservation.ReservationId);

        await _orders.AddAsync(order);
        _logger.LogInformation(
            "order_placed id={OrderId} customer={Customer} total={Total}",
            order.Id, order.CustomerId, reservation.TotalCents);

        return PlaceOrderResult.Accepted(order.Id);
    }

    public async Task<bool> CancelAsync(Guid orderId, string reason)
    {
        var order = await _orders.GetAsync(orderId);
        if (order is null) return false;
        if (order.Status == OrderStatus.Shipped) return false;

        await _payments.RefundAsync(order.PaymentToken);
        await _inventory.ReleaseAsync(order.ReservationId);
        order.Cancel(reason);
        await _orders.UpdateAsync(order);
        return true;
    }
}

public record PlaceOrderRequest(Guid CustomerId, IReadOnlyList<OrderLineItem> Items);

public record OrderLineItem(Guid SkuId, int Quantity);

public class PlaceOrderResult
{
    public bool IsAccepted { get; }
    public Guid? OrderId { get; }
    public string? RejectionReason { get; }

    private PlaceOrderResult(bool accepted, Guid? id, string? reason)
    {
        IsAccepted = accepted;
        OrderId = id;
        RejectionReason = reason;
    }

    public static PlaceOrderResult Accepted(Guid id) => new(true, id, null);
    public static PlaceOrderResult Rejected(string reason) => new(false, null, reason);
}
