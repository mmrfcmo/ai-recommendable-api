def _commercial_recommendation(score, signals):
    weakest=sorted(signals,key=lambda x:x["score"])[:2]
    names=[x["label"] for x in weakest]
    if score < 50:
        tier="Trust Transformation"; price="£995"; reason="The assessment identifies several foundational Trust Signal weaknesses that should be addressed before pursuing broader visibility or growth activity."
    elif score < 70:
        tier="AI Trust Optimisation"; price="£1,249"; reason="The business has a workable Trust Signal foundation, but several evidence and consistency gaps are limiting how clearly its digital representation is supported."
    else:
        tier="Advanced Visibility"; price="£1,995"; reason="The core Trust Signal foundation is comparatively strong, so the next priority is strengthening depth, consistency and external validation around the weakest areas."
    return {"recommended_treatment":tier,"indicative_price":price,"reason":reason,"priority_signals":names,"disclaimer":"Indicative recommendation based on this automated Trust Signals assessment. Final scope and price should be confirmed after human review."}

"""Shared Trust Signal assessment engine.
Basic and Deep modes use the same evidence model and six-signal taxonomy.
Scanner B is deliberately not modified by this module.
"""
import json, logging, re
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
    page_data=[]
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
    first=page_data[0]; soup=first["soup"]
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
    all_links=[a for p in page_data for a in p["soup"].find_all("a",href=True)]
    external_hrefs=[a.get("href","").lower() for a in all_links if a.get("href","").startswith(("http://","https://"))]
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
      ("Core service language repeats across pages",
       (len(page_data)==1 and bool(re.search(r"\b(?:services?|solutions?|consulting|specialist|professional)\b",all_text)))
       or (len(page_data)>1 and any(
           sum(bool(re.search(r"\b"+term+r"\b",p["text"].lower())) for p in page_data)>=2
           for term in ("service","services","solution","solutions","consulting","specialist","professional")
       ))),
      ("No obvious conflicting identity terms found",not bool(re.search(r"welcome to|we are [^.]{0,80}\b(?:different|formerly|previously)\b",all_text))),
    ]
    nc_score=_score([(ok,20) for _,ok in nc_e],100)
    nc_gaps=[x for x,ok in nc_e if not ok]

    # External Validation is deliberately evidence-aware, not fabricated.
    ev_limit=["This automated assessment does not claim to verify third-party directories, reviews, citations or external authority in full."]
    ev_e=[
      ("Website exposes links/references to external profiles or authorities",
       any(re.search(r"(linkedin\.com|facebook\.com|instagram\.com|trustpilot\.com|yell\.com|checkatrade\.com|yelp\.com|google\.com)",href) for href in external_hrefs)),
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
    # Translate binary evidence into commercially useful diagnostic context.
    advice={
      "Entity Clarity":{
        "Business identity appears consistently across assessed pages":("Identity is not consistently reinforced across the assessed site.","Inconsistent identity can make the business harder to interpret confidently across pages and systems.","Strengthen the repeated business identity, organisation description and core entity references."),
        "Clear H1 and page title are present":("Page-level identity is not consistently explicit.","Weak page-level identity can reduce clarity about what the business is and what each page represents.","Clarify page titles and H1s around the business, service and audience."),
        "About/company/purpose language is present":("The site does not clearly explain who the organisation is or what it does.","A visitor or system may have to infer the organisation's purpose rather than receiving a clear first-party explanation.","Strengthen the organisation and purpose narrative with concise first-party language."),
        "Organisation or LocalBusiness structured identity is present":("Machine-readable business identity is not sufficiently exposed.","Important entity information may be harder for systems to interpret consistently from the site itself.","Add or strengthen appropriate organisation/business structured identity and keep it aligned with visible content."),
        "Contact/location information is discoverable":("Business accountability or location information is not sufficiently clear.","Unclear accountability can weaken confidence and make the business entity harder to distinguish from alternatives.","Strengthen contact, location and accountability information."),
      },
      "Knowledge Completeness":{
        "Services/products are explicitly described":("Core services or products are not clearly described.","Visitors and systems may not have enough first-party information to understand exactly what the business provides.","Expand service/product descriptions with clear scope, audience, outcomes and supporting detail."),
        "Service/topic detail exists beyond navigation labels":("The assessed site contains limited substantive information beyond navigation-level descriptions.","Thin detail leaves important business knowledge implicit rather than explicitly represented.","Develop deeper service/topic content that answers practical customer questions."),
        "FAQ or question-answer content is present":("Common customer questions are not clearly answered on the assessed pages.","Important decision-stage knowledge may be missing when prospects are evaluating the business.","Add useful question-and-answer content around objections, process, suitability and common concerns."),
        "Expertise/experience is described":("The site's expertise or experience is not sufficiently evidenced.","Prospects may understand what is offered without understanding why this business is qualified to provide it.","Make relevant experience, expertise, qualifications and specialist capability explicit."),
        "Relevant locations/audience served are described":("The audience or geographic scope served is not sufficiently explicit.","Relevance can be harder to establish when the site does not clearly state who or where the business serves.","Clarify target audience, locations served and service-area relevance."),
        "Supporting content/resources are discoverable":("There is limited supporting content that develops the business's expertise.","The site has fewer opportunities to demonstrate depth, answer questions and reinforce its subject-matter authority.","Develop supporting resources such as guides, insights, FAQs or useful articles."),
      },
      "Trust Evidence":{
        "Reviews/testimonials are referenced":("Customer feedback is not sufficiently visible on the assessed pages.","Prospects may have less direct evidence that other customers have had a positive experience.","Surface relevant reviews, testimonials and customer feedback in context."),
        "Case studies/results/outcomes are present":("Specific outcomes or case evidence are not sufficiently demonstrated.","Claims are harder to evaluate when prospects cannot see concrete examples of results or outcomes.","Add concise case studies, examples, outcomes and before/after evidence where appropriate."),
        "Credentials/accreditations/awards are stated":("Credentials or recognised qualifications are not sufficiently evidenced.","The business may be credible in reality but the site does not make that credibility easy to verify.","Present relevant qualifications, accreditations, memberships and awards with context."),
        "Specific proof or client evidence is present":("Specific client or project evidence is limited.","Generic claims provide less confidence than identifiable examples of work, clients or projects.","Strengthen proof with appropriate client, project, portfolio or outcome evidence."),
        "Contact and business details support accountability":("Accountability details are not sufficiently visible.","Reduced transparency can make it harder for prospects to assess who stands behind the business.","Strengthen contact, business and accountability information."),
      },
      "Technical Accessibility":{
        "HTTPS is used":("The site is not consistently secured with HTTPS.","An insecure connection can undermine user confidence and technical trust.","Move all customer-facing pages and resources to HTTPS."),
        "Meta description is present":("A clear meta description is missing from the assessed page.","The page has less controlled explanatory context available to systems and users in search-style previews.","Add a concise, accurate description aligned with the page's purpose."),
        "Viewport is present":("Mobile viewport configuration is missing.","The page may provide weaker mobile presentation and accessibility signals.","Implement an appropriate responsive viewport configuration."),
        "Canonical URL is present":("A canonical URL is not clearly declared.","URL versioning can become less explicit when multiple address variants exist.","Add an appropriate canonical URL and keep URL signals consistent."),
        "Structured data is machine-readable":("Machine-readable structured data is limited or absent.","Important first-party information may rely more heavily on interpretation of page text.","Add appropriate structured data that reflects the visible business information."),
        "Robots/sitemap references are discoverable":("Robots or sitemap references are not clearly discoverable.","Technical discovery and site understanding may be less explicit than they could be.","Ensure robots and sitemap references are correctly exposed and aligned with the live site."),
        "Heading structure begins with a clear H1":("A clear primary heading is missing.","The page's primary subject is less explicit in its visible structure.","Introduce one clear, descriptive H1 aligned with the page purpose."),
      },
      "Narrative Consistency":{
        "Assessed pages have page titles":("Page titles are not consistently present.","The site's page-level narrative is less explicit and consistent.","Standardise meaningful page titles around service, audience and purpose."),
        "Assessed pages have clear H1s":("Primary headings are not consistently clear across assessed pages.","Visitors and systems may receive inconsistent cues about each page's purpose.","Strengthen H1 structure and align it with each page's actual purpose."),
        "Business identity is repeated consistently":("Business identity is not consistently reinforced across pages.","Different or incomplete identity cues can weaken the coherence of the overall business representation.","Create consistent organisation and brand references across key pages."),
        "Core service language repeats across pages":("Core service language is not consistently reinforced across the assessed pages.","The site's narrative may not build a strong, repeated understanding of what the business is known for.","Align service terminology across core pages and supporting content."),
        "No obvious conflicting identity terms found":("Potentially conflicting identity language was detected.","Conflicting descriptions can create ambiguity about the organisation, offer or positioning.","Review conflicting terminology and establish one consistent core narrative."),
      },
      "External Validation":{
        "Website exposes links/references to external profiles or authorities":("Relevant external profiles or authority references are not clearly connected from the site.","First-party claims have fewer visible connections to external validation sources.","Connect appropriate external profiles, professional bodies or authoritative references where genuinely relevant."),
        "Third-party validation is explicitly referenced":("Third-party validation is not clearly referenced on the assessed pages.","Prospects have fewer external trust cues to support the business's claims.","Surface relevant reviews, memberships, awards, media or professional validation with accurate context."),
        "Structured sameAs/external identity links are present":("Structured external identity relationships are not clearly declared.","The relationship between the business entity and its legitimate external profiles is less explicit.","Use appropriate sameAs relationships where they accurately represent the same business entity."),
      }
    }
    for sig in signals:
        sig["diagnostic_context"]=[]
        for gap in sig.get("gaps",[]):
            item=advice.get(sig["label"],{}).get(gap)
            if item:
                meaning,impact,action=item
                sig["diagnostic_context"].append({"finding":gap,"meaning":meaning,"business_impact":impact,"recommended_action":action})
        if not sig["diagnostic_context"]:
            sig["diagnostic_context"].append({"finding":"No major automated gap identified.","meaning":"The assessed evidence supports this Trust Signal.","business_impact":"This is a relative strength to preserve and reinforce.","recommended_action":"Maintain the signal and strengthen it with additional evidence as the site evolves."})
    score=round(sum(x["score"] for x in signals)/len(signals))
    strongest=max(signals,key=lambda x:x["score"]); weakest=min(signals,key=lambda x:x["score"])
    ranked=sorted(signals,key=lambda x:x["score"])
    priorities=[]
    for x in ranked[:4]:
        contexts=x.get("diagnostic_context",[])
        primary=contexts[0] if contexts else {
            "meaning":"Further evidence review is recommended.",
            "business_impact":"The available evidence is not sufficient to draw a stronger conclusion.",
            "recommended_action":"Review this area in more detail before deciding on treatment."
        }
        priorities.append({
            "signal":x["label"],
            "score":x["score"],
            "issue":primary.get("meaning","Further evidence review is recommended."),
            "meaning":primary.get("meaning","Further evidence review is recommended."),
            "business_impact":primary.get("business_impact","The available evidence is not sufficient to draw a stronger conclusion."),
            "recommended_action":primary.get("recommended_action","Review this area in more detail before deciding on treatment."),
            "evidence":x["evidence"][:2] if x.get("evidence") else []
        })
    weak_names=", ".join(x["label"] for x in ranked[:2])
    if score < 50:
        diagnosis=f"The assessment identifies foundational Trust Signal weaknesses, particularly in {weak_names}. The immediate priority is to strengthen the underlying representation and evidence before adding further activity."
        prescription="Strengthen the weakest Trust Signals first, then align the supporting content, technical signals and evidence so the website presents a clearer and more consistent representation of the business."
    elif score < 70:
        diagnosis=f"The website has a workable Trust Signal foundation, but {weak_names} stand out as areas where the digital representation could be clearer, better evidenced or more consistent."
        prescription="Address the weakest Trust Signals first, using the evidence identified in this assessment to improve clarity, supporting knowledge, trust evidence and consistency."
    else:
        diagnosis=f"The overall Trust Signal foundation is comparatively strong. The main opportunity is to strengthen the weaker areas, particularly {weak_names}, rather than making broad changes across the whole site."
        prescription="Preserve the stronger signals while improving the weaker areas with targeted evidence, clearer representation and greater consistency."
    synthesis={
        "diagnosis":diagnosis,
        "prescription":prescription,
        "strongest_signal":strongest["label"],
        "priority_signals":[x["label"] for x in ranked[:3]]
    }
    return {"success":True,"engine":"RbAI Trust Signal Engine","engine_version":"0.1","mode":mode,"url":url,"business_name":name,"pages_assessed":len(page_data),
            "pages_discovered":len(pages),"overall_score":score,"grade":"Leading" if score>=80 else "Strong" if score>=60 else "Developing" if score>=40 else "Needs Attention",
            "strongest_signal":strongest["label"],"weakest_signal":weakest["label"],"signals":signals,"priority_improvements":priorities,
            "diagnostic_synthesis":synthesis,
            "commercial_recommendation": _commercial_recommendation(score, signals),
            "limitations":["Basic mode assesses the homepage only." ] if mode=="basic" else ["Deep mode expands the crawl and evidence collection but does not guarantee complete external verification." ]}
