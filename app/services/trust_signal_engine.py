"""Shared Trust Signal assessment engine.
Basic and Deep modes use the same evidence model and six-signal taxonomy.
Scanner B is deliberately not modified by this module.
"""
import json, logging, re
from collections import Counter
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup

logger=logging.getLogger("rbai.trust_signal_engine")

SIGNALS=[
 ("entity_clarity","Entity Clarity"),
 ("knowledge_completeness","Knowledge Completeness"),
 ("trust_evidence","Trust Evidence"),
 ("technical_accessibility","Technical Accessibility"),
 ("narrative_consistency","Narrative Consistency"),
 ("external_validation","External Validation"),
]

def _url(u):
    return u if u.startswith(("http://","https://")) else "https://"+u

def _clean(s): return re.sub(r"\s+"," ",s or "").strip()

def _tokens(s):
    return set(re.findall(r"[a-z0-9]{3,}", (s or "").lower()))

def _jsonld(soup):
    out=[]
    for tag in soup.find_all("script",type="application/ld+json"):
        try:
            d=json.loads(tag.string or tag.get_text())
            if isinstance(d,dict) and "@graph" in d: out.extend(x for x in d["@graph"] if isinstance(x,dict))
            elif isinstance(d,list): out.extend(x for x in d if isinstance(x,dict))
            elif isinstance(d,dict): out.append(d)
        except Exception: pass
    return out

def _score(items, max_points):
    return min(max_points, sum(points for ok,points in items if ok))

def _signal(key,label,score,max_score,evidence,limitations=None,gaps=None):
    return {"name":key,"label":label,"score":round(score),"max_score":max_score,
            "percentage":round(score/max_score*100) if max_score else 0,
            "evidence":evidence[:8],"gaps":(gaps or [])[:8],"limitations":limitations or []}

async def assess(url, business_name=None, mode="basic"):
    url=_url(url.strip()); parsed=urlparse(url)
    root=f"{parsed.scheme}://{parsed.netloc}"
    pages=[url]
    max_pages=1 if mode=="basic" else 8
    timeout=12 if mode=="basic" else 10
    evidence=[]; page_data=[]
    headers={"User-Agent":"RbAI-TrustSignalsScanner/1.0"}
    async with httpx.AsyncClient(timeout=timeout,follow_redirects=True,headers=headers) as client:
        try:
            first=await client.get(url)
            first.raise_for_status()
        except Exception as exc:
            return {"success":False,"mode":mode,"url":url,"error":f"Unable to retrieve website: {str(exc)[:120]}",
                    "signals":[_signal(k,l,0,100,["Assessment could not retrieve the site."]) for k,l in SIGNALS]}
        def parse(page_url, html):
            soup=BeautifulSoup(html,"html.parser")
            text=_clean(soup.get_text(" ",strip=True)); title=_clean(soup.title.get_text() if soup.title else "")
            h1=[_clean(x.get_text(" ",strip=True)) for x in soup.find_all("h1")]
            h2=[_clean(x.get_text(" ",strip=True)) for x in soup.find_all("h2")]
            desc=""
            md=soup.find("meta",attrs={"name":re.compile("^description$",re.I)})
            if md: desc=_clean(md.get("content",""))
            links=[urljoin(page_url,a.get("href")) for a in soup.find_all("a",href=True)]
            internal=[x for x in links if urlparse(x).netloc==parsed.netloc and x.split("#")[0].startswith(root)]
            return {"url":page_url,"html":html,"soup":soup,"text":text,"title":title,"h1":h1,"h2":h2,
                    "desc":desc,"internal":list(dict.fromkeys(internal)),"jsonld":_jsonld(soup)}
        # Use the resolved URL after redirects for canonical host/scheme checks.
        url=str(first.url).split("#")[0]
        parsed=urlparse(url)
        root=f"{parsed.scheme}://{parsed.netloc}"
        pages=[url]
        first_data=parse(url,first.text); page_data.append(first_data)
        if mode=="deep":
            # Bounded breadth-first crawl: expand internal links from each assessed page
            # until the shared deep-mode page budget is reached.
            queue=list(first_data["internal"])
            seen=set(pages)
            while queue and len(pages)<max_pages:
                clean=queue.pop(0).split("#")[0]
                if clean in seen or urlparse(clean).path in ("/wp-admin/","/wp-login.php"):
                    continue
                seen.add(clean)
                try:
                    r=await client.get(clean)
                    if r.status_code>=400:
                        continue
                    resolved=str(r.url).split("#")[0]
                    if resolved in pages:
                        continue
                    data=parse(resolved,r.text)
                    pages.append(resolved)
                    page_data.append(data)
                    for child in data["internal"]:
                        child=child.split("#")[0]
                        if child not in seen and len(pages)+len(queue)<max_pages*2:
                            queue.append(child)
                except Exception as exc:
                    logger.info("deep page skipped %s: %s",clean,exc)

    texts=[p["text"] for p in page_data]; all_text=" ".join(texts).lower()
    first=page_data[0]; soup=first["soup"]; html=first["html"]
    name=business_name.strip() if business_name else ""
    if not name:
        # Prefer explicit Organization/LocalBusiness names from structured data.
        for j in first["jsonld"]:
            jtype=j.get("@type")
            types=jtype if isinstance(jtype,list) else [jtype]
            if any(str(t).lower() in {"organization","localbusiness","professionalservice","corporation"} for t in types):
                candidate=_clean(str(j.get("name","")))
                if candidate:
                    name=candidate
                    break
    if not name:
        name=(first["title"].split("|")[0].split("-")[0].strip() or parsed.netloc.split(".")[0]).strip()
    name_tokens=_tokens(name)
    identity_mentions=sum(1 for p in page_data if name_tokens and len(name_tokens & _tokens(p["text"]))>=max(1,min(2,len(name_tokens))))
    schema_types=[]
    for p in page_data:
        for j in p["jsonld"]:
            t=j.get("@type"); schema_types.extend(t if isinstance(t,list) else [t] if t else [])
    schema_text=" ".join(str(x) for x in schema_types).lower()

    # Entity Clarity: identity, purpose, contact/location, structured identity, cross-page consistency.
    ent_e=[]
    ent_e += [("Business identity appears consistently across assessed pages", identity_mentions>=max(1,len(page_data)//2),)]
    ent_e += [("Clear H1 and page title are present", bool(first["h1"]) and bool(first["title"]),)]
    ent_e += [("About/company/purpose language is present", bool(re.search(r"about us|about the|our company|we are|who we are|our story|founded|established",all_text)),)]
    ent_e += [("Organisation or LocalBusiness structured identity is present", bool(re.search(r"organization|localbusiness|professionalservice|corporation",schema_text)),)]
    ent_e += [("Contact/location information is discoverable", bool(re.search(r"contact us|telephone|phone|address|postcode|postal code|located in|based in",all_text)),)]
    ent_score=_score([(ok,20) for _,ok in ent_e],100)
    ent_gaps=[x for x,ok in ent_e if not ok]

    # Knowledge Completeness
    kn_e=[
      ("Services/products are explicitly described",bool(re.search(r"our services|services|what we do|products|solutions",all_text))),
      ("Service/topic detail exists beyond navigation labels",sum(len(p["text"].split()) for p in page_data)>=600 if mode=="deep" else len(first["text"].split())>=350),
      ("FAQ or question-answer content is present",bool(re.search(r"faq|frequently asked|common questions|how does|what is|why choose",all_text))),
      ("Expertise/experience is described",bool(re.search(r"experience|expert|specialist|qualified|years|accredited|certified",all_text))),
      ("Relevant locations/audience served are described",bool(re.search(r"serving|serve|based in|areas we cover|locations|local",all_text))),
      ("Supporting content/resources are discoverable",bool(re.search(r"blog|news|insights|guides|resources|articles",all_text))),
    ]
    kn_weights=[17,17,17,17,16,16]
    kn_score=_score([(ok,w) for (_,ok),w in zip(kn_e,kn_weights)],100)
    kn_gaps=[x for x,ok in kn_e if not ok]

    # Trust Evidence
    tr_e=[
      ("Reviews/testimonials are referenced",bool(re.search(r"reviews?|testimonials?|what our clients|customer feedback",all_text))),
      ("Case studies/results/outcomes are present",bool(re.search(r"case stud|results|success stor|outcomes|before and after",all_text))),
      ("Credentials/accreditations/awards are stated",bool(re.search(r"accredit|certif|award|member of|professional body",all_text))),
      ("Specific proof or client evidence is present",bool(re.search(r"clients include|trusted by|worked with|portfolio|projects",all_text))),
      ("Contact and business details support accountability",bool(re.search(r"contact|telephone|email|address|registered",all_text))),
    ]
    tr_score=_score([(ok,20) for _,ok in tr_e],100)
    tr_gaps=[x for x,ok in tr_e if not ok]

    # Technical Accessibility
    links=[a.get("href","") for a in soup.find_all("a",href=True)]
    ta_e=[
      ("HTTPS is used",url.startswith("https://")),
      ("Meta description is present",bool(first["desc"])),
      ("Viewport is present",bool(soup.find("meta",attrs={"name":re.compile("^viewport$",re.I)}))),
      ("Canonical URL is present",bool(soup.find("link",rel=lambda x:x and "canonical" in x))),
      ("Structured data is machine-readable",bool(first["jsonld"])),
      ("Robots/sitemap references are discoverable",bool(re.search(r"robots|sitemap",all_text+" "+" ".join(links),re.I))),
      ("Heading structure begins with a clear H1",bool(first["h1"])),
    ]
    ta_weights=[15,15,15,15,15,15,10]
    ta_score=_score([(ok,w) for (_,ok),w in zip(ta_e,ta_weights)],100)
    ta_gaps=[x for x,ok in ta_e if not ok]

    # Narrative Consistency: compare titles/H1 and repeated identity/service language across pages.
    titles=[p["title"] for p in page_data if p["title"]]; h1s=[x for p in page_data for x in p["h1"]]
    nc_e=[
      ("Assessed pages have page titles",len(titles)>=max(1,len(page_data)//2)),
      ("Assessed pages have clear H1s",len(h1s)>=max(1,len(page_data)//2)),
      ("Business identity is repeated consistently",identity_mentions>=max(1,len(page_data)//2)),
      ("Core service language repeats across pages",len(set(re.findall(r"\b(?:services?|solutions?|consulting|specialist|professional)\b",all_text)))>=2),
      ("No obvious conflicting identity terms found",not bool(re.search(r"welcome to|we are [^.]{0,80}\b(?:different|formerly|previously)\b",all_text))),
    ]
    nc_score=_score([(ok,20) for _,ok in nc_e],100)
    nc_gaps=[x for x,ok in nc_e if not ok]

    # External Validation is deliberately evidence-aware, not fabricated.
    ev_limit=["This automated assessment does not claim to verify third-party directories, reviews, citations or external authority in full."]
    ev_e=[
      ("Website exposes links/references to external profiles or authorities",bool(re.search(r"google|linkedin|facebook|instagram|trustpilot|yell|checkatrade|yelp|directory|association|professional body",all_text))),
      ("Third-party validation is explicitly referenced",bool(re.search(r"review|rating|accredit|member of|award|featured|press|media",all_text))),
      ("Structured sameAs/external identity links are present",any("sameas" in json.dumps(p["jsonld"]).lower() for p in page_data)),
    ]
    ev_weights=[34,33,33]
    ev_score=_score([(ok,w) for (_,ok),w in zip(ev_e,ev_weights)],100)
    ev_gaps=[x for x,ok in ev_e if not ok]
    signals=[
      _signal("entity_clarity","Entity Clarity",ent_score,100,[x for x,ok in ent_e if ok] or ["Limited clear entity evidence found."],gaps=ent_gaps),
      _signal("knowledge_completeness","Knowledge Completeness",kn_score,100,[x for x,ok in kn_e if ok] or ["Important business knowledge was not clearly found."],gaps=kn_gaps),
      _signal("trust_evidence","Trust Evidence",tr_score,100,[x for x,ok in tr_e if ok] or ["Limited direct trust evidence found."],gaps=tr_gaps),
      _signal("technical_accessibility","Technical Accessibility",ta_score,100,[x for x,ok in ta_e if ok] or ["Technical accessibility evidence is limited."],gaps=ta_gaps),
      _signal("narrative_consistency","Narrative Consistency",nc_score,100,[x for x,ok in nc_e if ok] or ["Narrative consistency needs deeper review."],gaps=nc_gaps),
      _signal("external_validation","External Validation",ev_score,100,[x for x,ok in ev_e if ok] or ["No strong external validation evidence was visible on the assessed pages."],ev_limit,ev_gaps),
    ]
    score=round(sum(x["score"] for x in signals)/len(signals))
    strongest=max(signals,key=lambda x:x["score"]); weakest=min(signals,key=lambda x:x["score"])
    priorities=sorted([{"signal":x["label"],"score":x["score"],"issue":(x["gaps"][0] if x.get("gaps") else "Further evidence review is recommended.")} for x in signals],key=lambda x:x["score"])[:4]
    return {"success":True,"engine":"RbAI Trust Signal Engine","engine_version":"0.1","mode":mode,"url":url,"business_name":name,"pages_assessed":len(page_data),
            "pages_discovered":len(pages),"overall_score":score,"grade":"Leading" if score>=80 else "Strong" if score>=60 else "Developing" if score>=40 else "Needs Attention",
            "strongest_signal":strongest["label"],"weakest_signal":weakest["label"],"signals":signals,"priority_improvements":priorities,
            "limitations":["Basic mode assesses the homepage only." ] if mode=="basic" else ["Deep mode expands the crawl and evidence collection but does not guarantee complete external verification." ]}
