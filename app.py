import random
import time
from datetime import datetime
from flask import Flask, jsonify, request
from models import db, Conversation, Message
from sqlalchemy import or_

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://messaging_user:messaging_password@localhost:5432/messaging_service'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()


def get_or_create_conversation(from_addr, to_addr):
    conversation = Conversation.query.filter(
        or_(
            (Conversation.participant_a == from_addr) & (Conversation.participant_b == to_addr),
            (Conversation.participant_a == to_addr) & (Conversation.participant_b == from_addr)
        )
    ).first()
    if conversation:
        return conversation
    conversation = Conversation(participant_a=from_addr, participant_b=to_addr, created_at=datetime.utcnow())
    db.session.add(conversation)
    db.session.commit()
    return conversation


def is_duplicate(provider_id):
    """Check if a message with the given provider_message_id already exists."""
    if not provider_id:
        return False
    return db.session.query(Message.id).filter_by(provider_message_id=provider_id).first() is not None


def mock_provider_send(provider_name, payload):
    """Simulate sending via provider with random transient failures."""
    max_retries = 3
    attempt = 0

    while attempt < max_retries:
        attempt += 1
        outcome = random.choice(["success", "500", "429"])
        if outcome == "success":
            return True, None
        elif outcome in ("500", "429"):
            wait_time = 2 ** attempt
            print(f"[Provider: {provider_name}] Error {outcome}, retrying in {wait_time}s...")
            time.sleep(wait_time)
        else:
            return False, f"Unexpected error: {outcome}"
    return False, "Provider failed after retries"


def parse_timestamp(ts):
    if not ts:
        return datetime.utcnow()
    if isinstance(ts, datetime):
        return ts
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


# API Endpoints 
@app.route('/api/messages/sms', methods=['POST'])
def send_sms():
    data = request.get_json()
    msg_type = data.get('type', 'sms').lower()

    # Validate attachment rules
    attachments = data.get('attachments') or []
    if msg_type == "sms" and attachments:
        return jsonify({"error": "SMS cannot have attachments"}), 400

    conversation = get_or_create_conversation(data.get('from'), data.get('to'))

    # Mock provider send
    success, error = mock_provider_send("twilio", data)
    if not success:
        return jsonify({"error": error}), 502

    message = Message(
        conversation_id=conversation.id,
        from_address=data.get('from'),
        to_address=data.get('to'),
        body=data.get('body'),
        message_type=msg_type,
        attachments=attachments,
        provider_message_id=data.get('messaging_provider_id'),
        timestamp=parse_timestamp(data.get('timestamp')),
    )

    db.session.add(message)
    db.session.commit()
    return jsonify({"message": f"{msg_type.upper()} sent to {data.get('to')}"}), 200


@app.route('/api/messages/email', methods=['POST'])
def send_email():
    data = request.get_json()
    conversation = get_or_create_conversation(data.get('from'), data.get('to'))

    success, error = mock_provider_send("sendgrid", data)
    if not success:
        return jsonify({"error": error}), 502

    message = Message(
        conversation_id=conversation.id,
        from_address=data.get('from'),
        to_address=data.get('to'),
        body=data.get('body'),
        message_type='email',
        attachments=data.get('attachments') or [],
        provider_message_id=data.get('xillio_id'),
        timestamp=parse_timestamp(data.get('timestamp')),
    )

    db.session.add(message)
    db.session.commit()
    return jsonify({"message": f"Email sent to {data.get('to')}"}), 200


@app.route('/api/webhooks/sms', methods=['POST'])
def incoming_sms_webhook():
    data = request.get_json()
    provider_id = data.get('messaging_provider_id')
    if is_duplicate(provider_id):
        return jsonify({"message": "Duplicate message ignored"}), 200

    conversation = get_or_create_conversation(data.get('from'), data.get('to'))

    message = Message(
        conversation_id=conversation.id,
        from_address=data.get('from'),
        to_address=data.get('to'),
        body=data.get('body'),
        message_type=data.get('type', 'sms'),
        attachments=data.get('attachments') or [],
        provider_message_id=provider_id,
        timestamp=parse_timestamp(data.get('timestamp'))
    )

    db.session.add(message)
    db.session.commit()
    return jsonify({"message": "Incoming SMS received successfully!"}), 200


@app.route('/api/webhooks/email', methods=['POST'])
def incoming_email_webhook():
    data = request.get_json()
    provider_id = data.get('xillio_id')
    if is_duplicate(provider_id):
        return jsonify({"message": "Duplicate message ignored"}), 200

    conversation = get_or_create_conversation(data.get('from'), data.get('to'))

    message = Message(
        conversation_id=conversation.id,
        from_address=data.get('from'),
        to_address=data.get('to'),
        body=data.get('body'),
        message_type='email',
        attachments=data.get('attachments') or [],
        provider_message_id=provider_id,
        timestamp=parse_timestamp(data.get('timestamp'))
    )

    db.session.add(message)
    db.session.commit()
    return jsonify({"message": "Incoming email received successfully!"}), 200


@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    conversations = Conversation.query.all()
    result = []
    for conversation in conversations:
        result.append({
            "id": conversation.id,
            "participants": [conversation.participant_a, conversation.participant_b],
            "created_at": conversation.created_at.isoformat()
        })
    return jsonify(result), 200


@app.route('/api/conversations/<int:id>/messages', methods=['GET'])
def get_messages_for_conversation(id):
    conversation = Conversation.query.get(id)
    if not conversation:
        return jsonify({"message": "Conversation not found"}), 404

    messages = Message.query.filter_by(conversation_id=id).order_by(Message.timestamp).all()
    result = []
    for message in messages:
        result.append({
            "from": message.from_address,
            "to": message.to_address,
            "body": message.body,
            "timestamp": message.timestamp.isoformat(),
            "type": message.message_type,
            "attachments": message.attachments or []
        })
    return jsonify(result), 200