import logging
from typing import List, Dict, Any, Optional
from pydantic import ValidationError
from app.schemas.order_operation import OrderOperation, OperationType

logger = logging.getLogger(__name__)

class OperationReducer:
    @staticmethod
    def _match_item_exact(op_dict: Dict, active_items: List[Dict]) -> List[int]:
        """Find the indices of items that match exact normalized raw product or target_operation_id."""
        target_id = op_dict.get("target_operation_id")
        matches = []

        # If target_operation_id is provided, match by it
        if target_id:
            for i, item in enumerate(active_items):
                if item.get("operation_id") == target_id:
                    matches.append(i)
            if matches:
                return matches

        # Otherwise exact normalized raw product match
        item_name = op_dict.get("raw_product", "").strip().lower()
        if not item_name:
            return []

        for i, item in enumerate(active_items):
            item_raw = str(item.get("raw_name", "")).strip().lower()
            if item_raw == item_name:
                matches.append(i)

        return matches

    @staticmethod
    def parse_and_reduce(raw_operations: List[Dict]) -> Dict[str, Any]:
        valid_ops = []
        invalid_operations = []

        # Parse safely
        for raw_op in raw_operations:
            try:
                op = OrderOperation(**raw_op)
                valid_ops.append(op.dict())
            except ValidationError as e:
                logger.warning(f"Invalid operation: {e}")
                invalid_operations.append({
                    "evidence": raw_op.get("evidence", str(raw_op)),
                    "error": str(e)
                })

        return OperationReducer.reduce(valid_ops, invalid_operations)

    @staticmethod
    def reduce(operations: List[Dict], invalid_operations: List[Dict] = None) -> Dict[str, Any]:
        if invalid_operations is None:
            invalid_operations = []

        active_items = []
        cancelled_items = []
        return_items = []
        substitution_instructions = []
        previous_order_reference = None
        operation_warnings = []

        # Sequence validation
        seen_seqs = set()
        valid_seq_ops = []
        for op in operations:
            seq = op.get("sequence")
            if seq is None or type(seq) not in (int, float) or seq < 0:
                invalid_operations.append({
                    "evidence": op.get("evidence", str(op)),
                    "error": f"Invalid or missing sequence: {seq}"
                })
            elif seq in seen_seqs:
                invalid_operations.append({
                    "evidence": op.get("evidence", str(op)),
                    "error": f"Duplicate sequence: {seq}"
                })
            else:
                seen_seqs.add(seq)
                valid_seq_ops.append(op)

        def get_seq(op):
            return op.get("sequence")

        sorted_ops = sorted(valid_seq_ops, key=get_seq)

        if invalid_operations:
            operation_warnings.append("Review Required: Unparseable or invalid operations detected.")

        from app.services.quantity_parser import parse_quantity

        for op_dict in sorted_ops:
            op_type = op_dict.get("type")
            raw_product = op_dict.get("raw_product", "")
            qty = op_dict.get("quantity")
            qty_raw = op_dict.get("quantity_raw", "")
            unit = op_dict.get("unit", "")
            evidence = op_dict.get("evidence", "")
            operation_id = op_dict.get("operation_id")

            # Priority 2: Use qty_raw if qty is missing
            if qty is None and qty_raw:
                parsed_qr = parse_quantity(qty_raw)
                if parsed_qr.get("quantity") is not None:
                    qty = parsed_qr["quantity"]
                if not unit and parsed_qr.get("unit"):
                    unit = parsed_qr["unit"]

            # Priority 3: raw_product parsing
            if raw_product:
                parsed_rp = parse_quantity(raw_product)
                if parsed_rp.get("quantity") is not None:
                    if qty is None:
                        qty = parsed_rp["quantity"]
                    if not unit and parsed_rp.get("unit"):
                        unit = parsed_rp["unit"]
                if parsed_rp.get("cleaned_text"):
                    raw_product = parsed_rp["cleaned_text"]

            # Priority 4: evidence parsing (only if unit is explicitly present to avoid arbitrary numbers)
            if (qty is None or not unit) and evidence:
                parsed_ev = parse_quantity(evidence)
                if qty is None and parsed_ev.get("quantity") is not None and parsed_ev.get("unit"):
                    qty = parsed_ev["quantity"]
                    if not unit:
                        unit = parsed_ev["unit"]
                elif not unit and parsed_ev.get("unit"):
                    unit = parsed_ev["unit"]

            if op_type == OperationType.ADD.value:
                active_items.append({
                    "operation_id": operation_id,
                    "name": raw_product,
                    "raw_name": raw_product,
                    "quantity": qty,
                    "unit": unit
                })
            elif op_type == OperationType.SET_QUANTITY.value:
                matches = OperationReducer._match_item_exact(op_dict, active_items)
                if len(matches) == 1:
                    idx = matches[0]
                    active_items[idx]["quantity"] = qty
                    if unit:
                        active_items[idx]["unit"] = unit
                    operation_warnings.append(f"Quantity corrected to {qty} {unit} for '{raw_product}'")
                elif len(matches) > 1:
                    operation_warnings.append(f"Ambiguity Warning: Multiple matches for SET_QUANTITY '{raw_product}'. Operation preserved in warnings.")
                else:
                    operation_warnings.append(f"Quantity update requested for '{raw_product}' but item not found in order.")
            elif op_type == OperationType.CANCEL.value:
                matches = OperationReducer._match_item_exact(op_dict, active_items)
                if len(matches) == 1:
                    idx = matches[0]
                    cancelled_items.append(active_items.pop(idx))
                    operation_warnings.append(f"Item cancelled: '{raw_product}'")
                elif len(matches) > 1:
                    operation_warnings.append(f"Ambiguity Warning: Multiple matches for CANCEL '{raw_product}'. Operation preserved in warnings.")
                else:
                    cancelled_items.append({"name": raw_product, "evidence": evidence})
                    operation_warnings.append(f"Cancellation requested for '{raw_product}' but item not found.")
            elif op_type == OperationType.RETURN.value:
                return_items.append({
                    "name": raw_product,
                    "quantity": qty,
                    "unit": unit,
                    "evidence": evidence
                })
                operation_warnings.append(f"Return requested: '{raw_product}'")
            elif op_type == OperationType.SUBSTITUTE.value:
                condition = op_dict.get("condition", "")
                substitution_instructions.append({
                    "name": raw_product,
                    "condition": condition,
                    "evidence": evidence
                })
                operation_warnings.append(f"Substitution requested for '{raw_product}': {condition}")
            elif op_type == OperationType.PREVIOUS_ORDER_REFERENCE.value:
                previous_order_reference = evidence
                operation_warnings.append(f"Previous order reference detected: '{evidence}'. Manual review required.")
            else:
                invalid_operations.append({
                    "evidence": evidence,
                    "error": f"Invalid operation type: {op_type}"
                })
                operation_warnings.append("Review Required: Invalid operation type detected.")

        return {
            "active_items": active_items,
            "cancelled_items": cancelled_items,
            "return_items": return_items,
            "substitution_instructions": substitution_instructions,
            "previous_order_reference": previous_order_reference,
            "invalid_operations": invalid_operations,
            "operation_warnings": operation_warnings
        }
