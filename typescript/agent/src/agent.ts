import { AIMessage, SystemMessage } from '@langchain/core/messages';
import { ChatBedrockConverse } from '@langchain/aws';
import { END, MessagesValue, START, StateGraph, StateSchema } from '@langchain/langgraph';
import { ToolNode } from '@langchain/langgraph/prebuilt';
import type { ConditionalEdgeRouter, GraphNode } from '@langchain/langgraph';
import process from 'node:process';

import { tools } from './tools.ts';

/** Cross-region inference profile for Claude Sonnet 4.5 on Bedrock. */
const DEFAULT_MODEL = 'us.anthropic.claude-sonnet-4-5-20250929-v1:0';
const DEFAULT_REGION = 'us-east-1';

const SYSTEM_PROMPT = [
  'You are a course assistant. You can list the pages in a course, read a single page, and update one.',
  'Find a page with list_course_pages when you do not already know its url — never guess a url.',
  'Read a page with get_course_page before you rewrite its body, so you do not discard content.',
  'Keep answers short and concrete.',
].join(' ');

/**
 * The agent's state is just the running message history. `MessagesValue`
 * supplies the reducer that appends each node's returned messages to it.
 */
export const AgentState = new StateSchema({ messages: MessagesValue });
export type AgentState = typeof AgentState.State;

const model = new ChatBedrockConverse({
  model: process.env['AGENT_MODEL'] ?? DEFAULT_MODEL,
  region: process.env['AGENT_AWS_REGION'] ?? process.env['AWS_REGION'] ?? DEFAULT_REGION,
  temperature: 0,
}).bindTools(tools);

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
