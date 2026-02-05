import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:bariatric_gpt/services/ai_service.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

class AiAssistantScreen extends StatefulWidget {
  const AiAssistantScreen({super.key});

  @override
  State<AiAssistantScreen> createState() => _AiAssistantScreenState();
}

class _AiAssistantScreenState extends State<AiAssistantScreen>
  with SingleTickerProviderStateMixin, AutomaticKeepAliveClientMixin {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final AiService _aiService = AiService();
  bool _isTyping = false;
  final FocusNode _textFocusNode = FocusNode();
  late final AnimationController _typingController;

  @override
  void initState() {
    super.initState();
    _typingController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
    // Scroll to bottom on load if we have history
    if (_aiService.messages.isNotEmpty) {
      _scrollToBottom();
    }
  }

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    _textFocusNode.dispose();
    _typingController.dispose();
    super.dispose();
  }

  @override
  bool get wantKeepAlive => true;

  Future<void> _sendMessage() async {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    // Add user message to persistent history
    final userMsg = ChatMessage(text: text, isUser: true);
    _aiService.addMessage(userMsg);

    setState(() {
      _isTyping = true;
    });

    _textController.clear();
    _scrollToBottom();

    // Call AI service
    final result = await _aiService.sendMessage(message: text);

    ChatMessage responseMessage;
    if (result['success']) {
      final md = result['response_markdown'];
      final plain = result['response'] ?? '';
      responseMessage = (md != null && md is String && md.isNotEmpty)
          ? ChatMessage(text: md, isUser: false, isMarkdown: true)
          : ChatMessage(text: plain, isUser: false, isMarkdown: false);
    } else {
      responseMessage = ChatMessage(
        text: 'Error: ${result['error']}',
        isUser: false,
      );
    }

    _aiService.addMessage(responseMessage);
    if (mounted) {
      setState(() {
        _isTyping = false;
      });
    }
    _scrollToBottom();
  }

  void _scrollToBottom() {
    // A small delay to allow the list to update before scrolling
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    // Access the persistent messages directly
    final messages = _aiService.messages;

    return Scaffold(
      body: Column(
        children: [
          // Chat messages
          Expanded(
            child: messages.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.chat_bubble_outline, size: 48, color: Colors.grey[300]),
                        const SizedBox(height: 16),
                        Text(
                          'Start a conversation...',
                          style: TextStyle(color: Colors.grey[500]),
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(16.0),
                    itemCount: messages.length,
                    itemBuilder: (context, index) {
                      final message = messages[index];
                      return _buildMessageBubble(message);
                    },
                  ),
          ),
          // "Typing" indicator
          if (_isTyping) _buildTypingIndicator(),
          // Text input field
          _buildTextInputArea(),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(ChatMessage message) {
    final align =
        message.isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start;
    final color = message.isUser
        ? Theme.of(context).primaryColor.withOpacity(0.8)
        : Colors.grey[200];
    final textColor = message.isUser ? Colors.white : Colors.black87;

    return Column(
      crossAxisAlignment: align,
      children: [
        Container(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.of(context).size.width * 0.75,
          ),
          margin: const EdgeInsets.symmetric(vertical: 4),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(16),
          ),
          child: message.isUser
              ? Text(
                  message.text,
                  style: TextStyle(color: textColor, fontSize: 16),
                )
              : (message.isMarkdown
                  ? MarkdownBody(
                      data: message.text,
                      styleSheet: MarkdownStyleSheet(
                        p: TextStyle(color: textColor, fontSize: 16),
                        h1: TextStyle(color: textColor, fontSize: 20, fontWeight: FontWeight.bold),
                        h2: TextStyle(color: textColor, fontSize: 18, fontWeight: FontWeight.bold),
                        // Adjust other styles as needed for dark/light mode
                      ),
                    )
                  : Text(
                      message.text,
                      style: TextStyle(color: textColor, fontSize: 16),
                    )),
        ),
      ],
    );
  }

  Widget _buildTextInputArea() {
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, -5),
          ),
        ],
      ),
      padding: EdgeInsets.only(
        left: 16,
        right: 8,
        top: 8,
        bottom: 8 + MediaQuery.of(context).padding.bottom,
      ),
      child: Row(
        children: [
          Expanded(
            child: Focus(
              onKey: (FocusNode node, RawKeyEvent event) {
                if (event is RawKeyDownEvent) {
                  final isShiftPressed = RawKeyboard.instance.keysPressed.contains(LogicalKeyboardKey.shiftLeft) ||
                      RawKeyboard.instance.keysPressed.contains(LogicalKeyboardKey.shiftRight);

                  if (event.logicalKey == LogicalKeyboardKey.enter || event.logicalKey == LogicalKeyboardKey.numpadEnter) {
                    if (isShiftPressed) {
                      // Insert newline at current cursor position
                      final text = _textController.text;
                      final sel = _textController.selection;
                      final start = sel.start >= 0 ? sel.start : text.length;
                      final end = sel.end >= 0 ? sel.end : text.length;
                      final newText = text.replaceRange(start, end, '\n');
                      final newOffset = start + 1;
                      _textController.text = newText;
                      _textController.selection = TextSelection.fromPosition(TextPosition(offset: newOffset));
                      return KeyEventResult.handled;
                    } else {
                      _sendMessage();
                      return KeyEventResult.handled;
                    }
                  }
                }
                return KeyEventResult.ignored;
              },
              child: TextField(
                controller: _textController,
                decoration: const InputDecoration(
                  hintText: 'Ask about diet, recovery, or medical questions...',
                  border: InputBorder.none,
                  filled: false,
                ),
                minLines: 1,
                maxLines: 5,
                textInputAction: TextInputAction.newline,
              ),
            ),
          ),
          IconButton(
            icon: Icon(Icons.send, color: Theme.of(context).primaryColor),
            onPressed: _sendMessage,
          ),
        ],
      ),
    );
  }

  Widget _buildTypingIndicator() {
    final dotColor = Theme.of(context).textTheme.bodyMedium?.color?.withOpacity(0.6) ?? Colors.grey;
    return Padding(
      padding: const EdgeInsets.all(8.0),
      child: Row(
        children: [
          const SizedBox(width: 4),
          AnimatedBuilder(
            animation: _typingController,
            builder: (context, child) {
              final t = _typingController.value;
              double dotOpacity(double offset) {
                final v = (t + offset) % 1.0;
                return (0.3 + 0.7 * (1 - (v - 0.5).abs() * 2)).clamp(0.3, 1.0);
              }

              return Row(
                children: [
                  _dot(dotColor.withOpacity(dotOpacity(0.0))),
                  const SizedBox(width: 6),
                  _dot(dotColor.withOpacity(dotOpacity(0.2))),
                  const SizedBox(width: 6),
                  _dot(dotColor.withOpacity(dotOpacity(0.4))),
                  const SizedBox(width: 10),
                  Text('Thinking...', style: TextStyle(color: dotColor)),
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _dot(Color color) {
    return Container(
      width: 6,
      height: 6,
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
      ),
    );
  }
}