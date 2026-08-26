import { AIMessage, SystemMessage } from '@langchain/core/messages';
import { END, MessagesValue, START, StateGraph, StateSchema } from '@langchain/langgraph';
import { ToolNode } from '@langchain/langgraph/prebuilt';
import type { ConditionalEdgeRouter, GraphNode } from '@langchain/langgraph';

import { createModel } from './model.ts';
import { tools } from './tools.ts';

const SYSTEM_PROMPT = [
  'You are a page assistant. You can list pages, read a single page, and update one.',
  'Find a page with list_pages when you do not already know its url — never guess a url.',
  'Read a page with get_page before you rewrite its body, so you do not discard content.',
  'Keep answers short and concrete.',
].join(' ');

/**
 * The agent's state is just the running message history. `MessagesValue`
 * supplies the reducer that appends each node's returned messages to it.
 */
export const AgentState = new StateSchema({ messages: MessagesValue });
export type AgentState = typeof AgentState.State;

/** Bedrock, the interview proxy, or the Gemini API — see `model.ts`. */
const model = createModel().bindTools(tools);

const callModel: GraphNode<typeof AgentState> = async (state) => {
  console.log('Thinking...');

  const response = await model.invoke([new SystemMessage(SYSTEM_PROMPT), ...state.messages]);

  // Return only the new message — the reducer appends it to the history.
  return { messages: [response] };
};

const shouldContinue: ConditionalEdgeRouter<{
  InputSchema: typeof AgentState;
  Nodes: 'tools';
}> = ({ messages }) => {
  const lastMessage = messages.at(-1);

  if (AIMessage.isInstance(lastMessage) && lastMessage.tool_calls?.length) {
    return 'tools';
  }
  return END;
};

export const agent = new StateGraph(AgentState)
  .addNode('agent', callModel)
  .addNode('tools', new ToolNode(tools))
  .addEdge(START, 'agent')
  .addEdge('tools', 'agent')
  .addConditionalEdges('agent', shouldContinue, ['tools', END])
  .compile();
