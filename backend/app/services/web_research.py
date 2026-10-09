from duckduckgo_search import DDGS


def build_queries(topic):
    """
    Generate multiple targeted research queries instead of
    sending the raw topic directly to search.
    """

    return [
        f'"{topic}" research study',
        f'"{topic}" academic research findings',
        f'"{topic}" systematic review',
        f'"{topic}" challenges benefits',
    ]


def search_web(query, max_results=3):

    queries = build_queries(query)

    results = []
    seen_urls = set()

    try:
        with DDGS() as ddgs:

            for search_query in queries:

                try:
                    items = ddgs.text(
                        search_query,
                        max_results=2
                    )

                    for item in items:

                        url = item.get("href", "")

                        if not url:
                            continue

                        if url in seen_urls:
                            continue

                        seen_urls.add(url)

                        title = item.get(
                            "title",
                            ""
                        )

                        content = item.get(
                            "body",
                            ""
                        )

                        # Ignore obvious irrelevant results
                        blocked_domains = [
                            "facebook.com",
                            "instagram.com",
                            "pinterest.com",
                            "impact.com",
                            "dictionary.com"
                        ]

                        if any(
                            domain in url.lower()
                            for domain in blocked_domains
                        ):
                            continue

                        results.append({
                            "source_type": "web",
                            "title": title,
                            "url": url,
                            "content": content
                        })

                        if len(results) >= max_results:
                            return results

                except Exception as error:

                    print(
                        "Search query failed:",
                        search_query,
                        repr(error)
                    )

                    continue

    except Exception as error:

        print(
            "Web search failed:",
            repr(error)
        )

    return results