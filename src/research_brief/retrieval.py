"""Local lexical retrieval scoped by the question's best matching topics."""
import re

from llama_index.core import QueryBundle
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore,TextNode

from .sources import record_hash,render,sha

STOPWORDS={'a','about','and','are','do','for','in','is','of','on','say','the','what'}


def terms(text):return set(re.findall(r'[a-z0-9]+',text.casefold()))-STOPWORDS


class LexicalSourceRetriever(BaseRetriever):
    def __init__(self,sources,top_k=5,on_retrieval=None):
        super().__init__()
        if type(top_k) is not int or not 1<=top_k<=20:raise ValueError('top_k must be an integer from 1 to 20')
        self.top_k=top_k;self.records=tuple(sources);self.on_retrieval=on_retrieval
        self.search_text={r['source_id']:terms(' '.join([r['title'],r['topic'],*r['tags'],r.get('method') or '',str(r.get('sample_size') or ''),r['text']])) for r in sources}
        self.topic_terms={r['topic']:terms(r['topic']) for r in sources}

    @property
    def nodes(self):
        return [TextNode(id_=r['source_id'],text=render(r),metadata={**{key:r[key] for key in ('source_id','title','published','topic','claim_key','claim_value')},
            'record_sha256':record_hash(r),'source_text_sha256':sha(r['text'].encode())}) for r in self.records]

    def _retrieve(self,query_bundle:QueryBundle):
        query_terms=terms(query_bundle.query_str)
        topic_scores={topic:len(query_terms&vocabulary) for topic,vocabulary in self.topic_terms.items()}
        highest=max(topic_scores.values(),default=0)
        topics={topic for topic,score in topic_scores.items() if not highest or score==highest}
        ranked=[]
        for node in self.nodes:
            if node.metadata['topic'] not in topics:continue
            score=len(query_terms&self.search_text[node.metadata['source_id']])
            if score:ranked.append(NodeWithScore(node=node,score=float(score)))
        ranked.sort(key=lambda item:(-item.score,item.node.metadata['source_id']))
        selected=ranked[:self.top_k]
        if self.on_retrieval:self.on_retrieval({'question':query_bundle.query_str,'topic_scores':topic_scores,'selected_topics':sorted(topics),
            'matching_count':len(ranked),'truncated':len(ranked)>self.top_k,'nodes':[{'source_id':item.node.metadata['source_id'],'score':item.score,'context_sha256':sha(item.node.text.encode()),'record_sha256':item.node.metadata['record_sha256']} for item in selected]})
        return selected

    async def _aretrieve(self,query_bundle):return self._retrieve(query_bundle)
