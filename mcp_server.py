from typing import Dict, List
import httpx
import json
import requests
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("GrabMart")


# @mcp.tool(name="greeting")
# def greeting_message(query: str) -> str:
#     """
#     Welcome tool for GrabMart MCP server.

#     This tool provides a welcome message for users interacting with the GrabMart MCP.
#     Always Use this tool (irrespective of user query) for general chat interactions while other tools are under maintenance.

#     Args:
#         query: The user's input query (currently not processed)

#     Returns:
#         str: A welcome message introducing the GrabMart MCP system
#     """
#     return "Welcome to GrabMart MCP! This system was developed by Team Vertex for GrabHack."

GLOBAL_COOKIE  = "_gcl_au=1.1.1677865953.1751578638; x_forwarded_host=mart.grab.com; subpath=%7B%22countryCode%22%3A%22SG%22%2C%22lang%22%3A%22en%22%7D; _gsvid=ae7f33ba-d760-4e80-8570-ea1b564ad4e5; _hjSessionUser_1532049=eyJpZCI6ImNhYzI3MmMzLWJjOTMtNWM4MC1hODJjLWMxY2YwZTQ2MzZiMCIsImNyZWF0ZWQiOjE3NTE1Nzg2Mzc4MjgsImV4aXN0aW5nIjp0cnVlfQ==; user_place=%7B%22poiID%22%3A%22IT.12L5XDMEOBJQH%22%2C%22address%22%3A%22321%20Orchard%20Rd%2C%20Singapore%2C%20238866%22%2C%22location%22%3A%7B%22latitude%22%3A1.3015272218817273%2C%22longitude%22%3A103.83787487005014%7D%2C%22name%22%3A%22Orchard%20Shopping%20Centre%22%2C%22city%22%3A%22Singapore%20City%22%2C%22cityID%22%3A%226%22%2C%22country%22%3A%22Singapore%22%2C%22countryID%22%3A%224%22%7D; _gid=GA1.2.226543169.1751736174; _ga=GA1.1.484099127.1751578637; _ga_65FYNH52KQ=GS2.1.s1751736174$o3$g0$t1751736181$j53$l0$h1751733148; grabid-openid-authn-ck=eyJhbGciOiJSUzI1NiIsImtpZCI6Il9kZWZhdWx0IiwidHlwIjoiSldUIn0.eyJhbXIiOiJXRUJMT0dJTiIsImF1ZCI6IlNTT19UT0tFTl9JU1NVSU5HX1NFUlZJQ0UiLCJlc2kiOiJJSUo5ckx3NmRrZ0JOWGIvaU1zZ1BZRjFSaGY2SE9zR2g3ZjF5STNENm5VOHRta1dVdz09IiwiZXhwIjoxNzU2OTIxNzAyLCJpYXQiOjE3NTE3Mzc2OTksImp0aSI6ImVlOWM2MmI5LTNkNmYtNDMwMy1iODViLTEzMDNiZjRmMTU0ZCIsInN1YiI6IjU2ZDgyYjYxLTc2YjAtNDhkYy04NTJkLWFjODRmYzZhNTcyOSIsInN2YyI6IlBBU1NFTkdFUiJ9.aKBsDRSLju3PHsErQBNgwnHjHdyHIx0p5DvdSx3McJj0-Qcpu5pIGAjDCtbnnq-uJTjJCc8AlBP-2PaH5JtMhsQmK2xkWUaDEeeUDKf0tXRf2hGJ2DW-ZGb9pD_onuBc6xEdxzmSqi9T6cN8XnZakq4oXQ9Nq7CI7mlby7enGqHCOWXKmQSE4NlUIVICbF1_NUm5FwGs7eGBwKqVe-CM7RJF8BvIVdqt0DACzjd2nIuIdDFRYICv9aAq1kJykOJamz8rHKIbHeCONw7gAIKKGc1BtyRV5jtrb7oEKxpGJpGQu_-DBWpRS-aPjaE3MxUgxI9xqlZqYoxuxsjBKGOZsA; _gssid=2506052135-o5sak47muws; OptanonConsent=isGpcEnabled=0&datestamp=Sun+Jul+06+2025+03%3A05%3A58+GMT%2B0530+(India+Standard+Time)&version=202304.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1&geolocation=IN%3BKA&AwaitingReconsent=false; OptanonAlertBoxClosed=2025-07-05T21:35:58.305Z; grabid_login_info=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0b2tlbiI6ImV5SmhiR2NpT2lKU1V6STFOaUlzSW10cFpDSTZJbDlrWldaaGRXeDBJaXdpZEhsd0lqb2lTbGRVSW4wLmV5SmhkV1FpT2lJelpqYzNOVFExTTJJM01UazBPRGxpWWpreE5qSTFPV0prWmpsaE9UYzBZU0lzSW1GMWRHaGZkR2x0WlNJNk1UYzFNVGN6TnpZNU9Td2laWGh3SWpveE56VXhOemczTXpVM0xDSnBZWFFpT2pFM05URTNOVEV6TlRjc0ltbHpjeUk2SW1oMGRIQnpPaTh2YVdSd0xtZHlZV0l1WTI5dElpd2lhblJwSWpvaVFrbFpNRmxJYVhkVVRrZHdkR0pYZEZGM05pMUdkeUlzSW01aVppSTZNVGMxTVRjMU1URTNOeXdpY0dsa0lqb2lOVFptTUdKaE1tWXRPV1ExTWkwME56azJMVGcwTmpjdE9HTmlZekV5TVRjMFpUQmtJaXdpYzJOd0lqb2lXMXdpYjNCbGJtbGtYQ0lzWENKd2NtOW1hV3hsTG5KbFlXUmNJaXhjSWpFNU1ESTFaV0ZoTnpFNE9UUmxZelppTnpjeFpEUTNPV0ZrWW1NM1lUUmhYQ0pkSWl3aWMzVmlJam9pTFdsVE5EZG5UM0Y0WkU0NGFEQlBTVTFyZFdSWlVTMUhWeTF0Y1hCelZrWlNVRFZ6YWt0TGVETmpXbEpuSWl3aWMzWmpJam9pVUVGVFUwVk9SMFZTSWl3aWRHdGZkSGx3WlNJNkltRmpZMlZ6Y3lKOS54V1hya00zRm5FYVVzTlR2M3prUFM5NnljTE54LTllUV9EcGg4X1AzMnZwT1JFZk02ejF3Tk9vRmdpM1lyaExsV19IUWo2YUFGdG1xTXIzdUtwRFlYbGdkQ1dJQjgzTUJidFA2T1FaN1M2TzF1VzAxdFk3bjlxMXNPRVN6U1doTnVCandWVlhzYkRQaGstUGZjbk5aaG4wZHhNZEZObzJRWVlUTmxfcUxKZDNGNThCbm5FLXk4LWJLUlpwbjdaUHVQWUNnS0Vra0xncHdIQk9oTnRxM1ZFOWptR2dGVjdURE9WYlZJOGxybmRpOU9HaENRb2F3c09PNkgwb3EyZzh0V1dvRVBBQWZSekxvTjE3RGU5cXF5TGozTXRETklCajVGQzhBamVBQ0g2VGJ1VTVUX0doLTJjVmIxcDczUjUyZkJwdldxOHkwNFc2aDlLYmRmd0FDQ0EiLCJleHBpcmVzSW4iOjM1OTk5LCJpc3N1ZWRBdCI6MTc1MTc1MTM1Nzk3MiwidHRsRXh0ZW5kZWRBdCI6MTc1MTc1MTM1ODg0MCwibmFtZSI6IlBhdGhpayIsInNhZmVJZCI6IjU2ZDgyYjYxLTc2YjAtNDhkYy04NTJkLWFjODRmYzZhNTcyOSIsImFwcE5hbWUiOiJPUkRFUklORyJ9.xaLVTPo20wehwbgbx4jAjx-h2BIQ_aDjAR_JbEBJ-H0; _ga_1D6Y4KQWXN=GS2.1.s1751751350$o8$g1$t1751751371$j39$l0$h0"

@mcp.tool(name="product_search")
def search_products(keyword: str):
    """
    Search for keyword on GrabMart using the provided keyword.

    This tool searches for keyword available on GrabMart by making an API request
    to the GrabMart search endpoint. It returns information about merchants that
    sell the specified keyword, including their details, ratings, delivery fees,
    and estimated delivery times.

    Args:
        keyword (str): The search keyword/product name to search for on GrabMart

    Returns:
        List[Dict]: A list of merchant dictionaries containing:
            - id (str): Merchant ID
            - name (str): Merchant/store name
            - photoUrl (str): URL to merchant's photo/image
            - distanceInKm (float): Distance from user location in kilometers
            - rating (float): Merchant's rating value
            - estimatedDeliveryFee (float): Estimated delivery fee in local currency
            - estimatedDeliveryTime (int): Estimated delivery time in minutes

        Returns None if the API request fails or no results are found.

    Note:
        Results are sorted by distance (closest merchants first) and limited to top 5 results.
        The search uses a fixed location in Singapore (Orchard Towers area).
    """

    url = "https://mart.grab.com/martwebapi/v1/protected/search?latitude=1.3069680322828752&longitude=103.82914473672564&keyword={keyword}&offset=0&size=20&requireSortAndFilters=true&dryrunSortAndFilters=false&filters="
    payload = {}
    headers = {
        "accept": "*/*",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "priority": "u=1, i",
        "referer": f"https://mart.grab.com/sg/en/merchant?keyword={keyword}",
        "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "x-country-code": "SG",
        "x-grab-web-app-version": "112403446",
        "Cookie": GLOBAL_COOKIE,
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    if response.status_code != 200:
        print(response.status_code)
        return None

    data = response.json()
    merchants = data.get("searchResult", {}).get("searchMerchants", [])

    result = []

    for m in merchants:
        result.append(
            {
                "id": m.get("id", ""),
                "name": m.get("address", {}).get("name", ""),
                "latitude": m.get("latlng", {}).get("latitude", 0.0),
                "longitude": m.get("latlng", {}).get("longitude", 0.0),
                "photoUrl": m.get("merchantBrief", {}).get("photoHref", ""),
                "distanceInKm": m.get("merchantBrief", {}).get(
                    "distanceInKm", float("inf")
                ),
                "rating": m.get("merchantBrief", {}).get("rating", 0),
                "estimatedDeliveryFee": m.get("estimatedDeliveryFee", {}).get(
                    "price", 0
                ),
                "estimatedDeliveryTime": m.get("estimatedDeliveryTime", 0),
            }
        )

    result_sorted = sorted(result, key=lambda x: x["distanceInKm"])
    return result_sorted[:5]


@mcp.tool(name="merchant_product_pairs")
def merchant_product_pair_search(merchant_id: str, keywords: List[str], lat: str, lng: str):
    """
    Search for product-items within a specific merchant using keyword and location.

    This function queries the GrabMART API to find products matching the given keyword
    within a specific merchant's inventory. It uses the merchant's ID and location
    coordinates to perform the search.

    Args:
        merchant_id (str): The unique identifier of the merchant to search within
        keywords (List[str]): The search terms to find matching products
        lat (str): Latitude coordinate of the search location
        lng (str): Longitude coordinate of the search location

    Returns:
        list: A list of dictionaries containing product information. Each dictionary
              includes:
              - id (str): Product identifier
              - name (str): Product name
              - price (int): Product price (SGD) in display format
              - img_url (str): URL to product image
              - weight (str): Product weight information

    Note:
        Returns an empty list if the API request fails or no products are found.
        The function uses async HTTP requests to fetch data from GrabMART's API.
    """
    url = f"https://mart.grab.com/martwebapi/v1/protected/merchants/{merchant_id}/search"
    merchant_result = {"merchant_id":merchant_id, "items": {}}
    for keyword in keywords:
        if not keyword.strip():
            continue
        params = {
            "keyword": keyword,
            "merchantID": merchant_id,
            "latlng": f"{lat},{lng}",
            "size": 24,
            "offset": 0
        }
        headers = {
            "accept": "*/*",
            "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
            "priority": "u=1, i",
            "referer": f"https://mart.grab.com/sg/en/merchant/{merchant_id}?keyword={keyword}",
            "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            "x-nextjs-data": "1",
            "Cookie": GLOBAL_COOKIE,
        }

        response = requests.get(url, params=params, headers=headers)
        if response.status_code != 200:
            return []

        data = response.json()
        items = data.get("items", [])[:3]
        result = []
        result=[]
        for item in items:
            result.append({
                "id": item.get("ID", ""),
                "name": item.get("name", ""),
                "price": item.get("priceV2", {}).get("amountDisplay", 0),
                "img_url": item.get("imgHref", ""),
                "weight": item.get("itemAttributes", {}).get("displayedTexts", {}).get("weight", "")
            })
        merchant_result["items"][keyword] = result
    return merchant_result


@mcp.tool(name="json_format")
def return_recommendation(recommendation_json: Dict) -> Dict:
    """
    Returns the recommendation JSON as provided.
    
    Args:
        recommendation_json: A JSON containing the recommendation data with merchant details,
                           available items, pricing, and delivery information.
    
    Returns:
        The recommendation JSON as provided.
    """
    try:
        # Validate that the input is valid JSON
        return recommendation_json
    except json.JSONDecodeError:
        return {"error": "Invalid JSON format provided"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
