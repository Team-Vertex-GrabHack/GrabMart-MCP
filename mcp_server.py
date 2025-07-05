from typing import Dict, List
import httpx
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

    url = "https://mart.grab.com/martwebapi/v1/protected/search?latitude=1.3069680322828752&longitude=103.82914473672564&keyword=tomato&offset=0&size=20&requireSortAndFilters=true&dryrunSortAndFilters=false&filters="

    payload = {}
    headers = {
        "accept": "*/*",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "priority": "u=1, i",
        "referer": f"https://mart.grab.com/sg/en/search?keyword={keyword}",
        "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "x-country-code": "SG",
        "x-grab-web-app-version": "112403446",
        "Cookie": "_gcl_au=1.1.990857068.1748253307; _fbp=fb.1.1748253307697.20834380470971499; x_forwarded_host=mart.grab.com; _gsvid=2378cd82-de90-4654-a806-3bde0b951772; subpath=%7B%22countryCode%22%3A%22SG%22%2C%22lang%22%3A%22en%22%7D; _hjSessionUser_1532049=eyJpZCI6IjI2ZmRkMjk2LWVmNTgtNTc5OC04MmIwLWMxZDRhY2Y2OTkxZiIsImNyZWF0ZWQiOjE3NDgyNTMzMDczOTAsImV4aXN0aW5nIjp0cnVlfQ==; user_place=%7B%22poiID%22%3A%22IT.1SEE5T4K0RMOL%22%2C%22address%22%3A%22400%20Orchard%20Rd%2C%20%2304-02%2C%20Singapore%2C%20238875%22%2C%22location%22%3A%7B%22latitude%22%3A1.3069680322828752%2C%22longitude%22%3A103.82914473672564%7D%2C%22name%22%3A%22LaPasta%20-%20Orchard%20Towers%22%2C%22city%22%3A%22Singapore%20City%22%2C%22cityID%22%3A%226%22%2C%22country%22%3A%22Singapore%22%2C%22countryID%22%3A%224%22%7D; grabid-openid-authn-ck=eyJhbGciOiJSUzI1NiIsImtpZCI6Il9kZWZhdWx0IiwidHlwIjoiSldUIn0.eyJhbXIiOiJXRUJMT0dJTiIsImF1ZCI6IlNTT19UT0tFTl9JU1NVSU5HX1NFUlZJQ0UiLCJlc2kiOiJlQ3diS2lmeHBnaldyU0pOMXhOUXFXeEgrOEtTc2pOM3RYbjFvcm9rcWRJV2V3bCtSUT09IiwiZXhwIjoxNzU2ODgxMjY0LCJpYXQiOjE3NTE2OTcyNjEsImp0aSI6ImVhMGFiNWJlLWNkOWItNDMwMi04ODgwLWMzYjcyMjBlNTllMiIsInN1YiI6IjVjNWMyYWY3LWE1NmMtNGQ0ZC1iNjhjLTAxN2VmNTkyZjk1NiIsInN2YyI6IlBBU1NFTkdFUiJ9.gZxNzD4v5kvhBCBqXaAC3ogDr6wjbAGXdpiCBWqS2cMBWmdAqq_tFwYw28_VYL2L0osNC6loRnl96LGpuUe2G25ACfuW5oasn8DA5b8NO0vV_WnpqOOAlrfTBGfYeW_tPjRan64v1KlaKcitZP6z2EN96iv4W6RPCVIrTCdwRAyLBJKMmBVwjVHRmavxaisiyf-RFcPACfaK7GLYtzUjhVzSM9FkAguoKoerHP2CsyRf87vcTDqNRvYKqcO6vHOy4y-bYgGEY2OnvYYdPPLrpi4WmWPRZl4AH3OtD5MjgGGP9CIS73nH_AA7UqnMUv5AaRdXYP2QnSmJEWHscKX87Q; hwuuid=9af1d5a6-3236-41f1-86be-e90b6b6f5d14; hwuuidtime=1751697315; _gssid=2506051307-z5sa0198ul; utm_source=Google; utm_medium=non-paid; _gid=GA1.2.395878170.1751722142; _ga=GA1.1.1124394898.1748253306; _ga_65FYNH52KQ=GS2.1.s1751722143$o3$g0$t1751722143$j60$l0$h2106696239; _hjSession_1532049=eyJpZCI6Ijg4ZTFlYTY0LWZjZDYtNGU2ZS1iYzEyLWI4YTllMTIzOWEwYSIsImMiOjE3NTE3MjIxNDMzNTgsInMiOjAsInIiOjAsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjowLCJzcCI6MH0=; OptanonConsent=isGpcEnabled=0&datestamp=Sat+Jul+05+2025+19%3A08%3A56+GMT%2B0530+(India+Standard+Time)&version=202304.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1&geolocation=IN%3BKA&AwaitingReconsent=false; OptanonAlertBoxClosed=2025-07-05T13:38:56.522Z; grabid_login_info=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0b2tlbiI6ImV5SmhiR2NpT2lKU1V6STFOaUlzSW10cFpDSTZJbDlrWldaaGRXeDBJaXdpZEhsd0lqb2lTbGRVSW4wLmV5SmhkV1FpT2lJelpqYzNOVFExTTJJM01UazBPRGxpWWpreE5qSTFPV0prWmpsaE9UYzBZU0lzSW1GMWRHaGZkR2x0WlNJNk1UYzFNVFk1TnpJMk1Td2laWGh3SWpveE56VXhOelU0TnpNM0xDSnBZWFFpT2pFM05URTNNakkzTXpjc0ltbHpjeUk2SW1oMGRIQnpPaTh2YVdSd0xtZHlZV0l1WTI5dElpd2lhblJwSWpvaVMxTmxkRU56TVdWU0xTMTVUMU10YzJWRVJWVjVVU0lzSW01aVppSTZNVGMxTVRjeU1qVTFOeXdpY0dsa0lqb2lOVFptTUdKaE1tWXRPV1ExTWkwME56azJMVGcwTmpjdE9HTmlZekV5TVRjMFpUQmtJaXdpYzJOd0lqb2lXMXdpYjNCbGJtbGtYQ0lzWENKd2NtOW1hV3hsTG5KbFlXUmNJaXhjSWpFNU1ESTFaV0ZoTnpFNE9UUmxZelppTnpjeFpEUTNPV0ZrWW1NM1lUUmhYQ0pkSWl3aWMzVmlJam9pTFdsVE5EZG5UM0Y0WkU0NGFEQlBTVTFyZFdSWlVTMW9jakJ2VjJwT1pVNDRXVU5sTjNWNVlUaHpTVU5SSWl3aWMzWmpJam9pVUVGVFUwVk9SMFZTSWl3aWRHdGZkSGx3WlNJNkltRmpZMlZ6Y3lKOS5QQU9UR2ZiZGduNDF4a2JfeWM5UW5mUXJUdDlnSDZMN2hFZlM5ZFlpbmFsbXVjdkZJMTMxbU1TZFk0Vld2MkotSno1alV4cXZIZVZqRUw1VXJDZjU0c0pKYVExNzhSQlFVNDg2Wkw4elE5SU5fcVpia01ZZjNqams1cTJyaFZkYkxaVFBTVmUxaUFXSUxaNTY0S25XbTM2YWtYUlBCN0VXVFY2QUQtS2JYVElQNlc2TjRsZVRicy1JT3M4ZkxUQmxUUWxSTC1OVkZrc253TmlyZ3RRSGpXZm1TLWVnWEVDVV9uVWJHZHoyNkZtQ3pYYkRrLWxwQnFCdVVLaU1kM0l1TzhLWURfeTRtS1JNcUYzYktnRk95S3lOajdlSW9FSllGcnF3MkNNdnlnM3FGLWJScGh6OXBjMElZb1p4SFlUX0xtck5fTTEzOGhudktxenBrSTNKSkEiLCJleHBpcmVzSW4iOjM1OTk5LCJpc3N1ZWRBdCI6MTc1MTcyMjczNzUxNiwidHRsRXh0ZW5kZWRBdCI6MTc1MTcyMjczODMxOSwibmFtZSI6Im11c2thbiBhZ2Fyd2FsIiwic2FmZUlkIjoiNWM1YzJhZjctYTU2Yy00ZDRkLWI2OGMtMDE3ZWY1OTJmOTU2IiwiYXBwTmFtZSI6Ik9SREVSSU5HIn0.bthquS4G99pRlLdf684OcjZYsLLrqT2xuD-LR5VC804; _ga_1D6Y4KQWXN=GS2.1.s1751720871$o11$g1$t1751722741$j44$l0$h0; grabid_login_info=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0b2tlbiI6ImV5SmhiR2NpT2lKU1V6STFOaUlzSW10cFpDSTZJbDlrWldaaGRXeDBJaXdpZEhsd0lqb2lTbGRVSW4wLmV5SmhkV1FpT2lJelpqYzNOVFExTTJJM01UazBPRGxpWWpreE5qSTFPV0prWmpsaE9UYzBZU0lzSW1GMWRHaGZkR2x0WlNJNk1UYzFNVFk1TnpJMk1Td2laWGh3SWpveE56VXhOelUyT1RjMUxDSnBZWFFpT2pFM05URTNNakE1TnpVc0ltbHpjeUk2SW1oMGRIQnpPaTh2YVdSd0xtZHlZV0l1WTI5dElpd2lhblJwSWpvaU1HUkdUMjA0V0RKUk4xZGFZelowWWpkV0xYQlNaeUlzSW01aVppSTZNVGMxTVRjeU1EYzVOU3dpY0dsa0lqb2lOVFptTUdKaE1tWXRPV1ExTWkwME56azJMVGcwTmpjdE9HTmlZekV5TVRjMFpUQmtJaXdpYzJOd0lqb2lXMXdpYjNCbGJtbGtYQ0lzWENKd2NtOW1hV3hsTG5KbFlXUmNJaXhjSWpFNU1ESTFaV0ZoTnpFNE9UUmxZelppTnpjeFpEUTNPV0ZrWW1NM1lUUmhYQ0pkSWl3aWMzVmlJam9pTFdsVE5EZG5UM0Y0WkU0NGFEQlBTVTFyZFdSWlVTMW9jakJ2VjJwT1pVNDRXVU5sTjNWNVlUaHpTVU5SSWl3aWMzWmpJam9pVUVGVFUwVk9SMFZTSWl3aWRHdGZkSGx3WlNJNkltRmpZMlZ6Y3lKOS5NMFFoOUh6NEZwSTh4cWhsRURsd2hhUi0yR1Q1UnJodDRYVVZWcGxUNkNlWTdsY3hHbkxhMlpmQlpLbDVFaUIyaXVHQ0hTQ2lpSkZLeGFONEFjYUViaGtrS3dHT1ctRE9UVU1TZjdocDliVnp1UTZmSE5JY1dJSHFOMVl0VGtLaEtuZE1fbjl0TWpHNnY2Q1lGV0JzQmdkdk04MDM3d3pKYllwMTBSREFJTVF2bWJtRmdfellIWElJSU1MQkVBMFJNbm4yVDN4cDJtUWFpZ1NvekdEeWduTlh3a09tbjVJRjczVUV1V0xVRjYxdkN0VGlTdU9uZGNic29Zdm4xaUZBOHBoVEF0MlVRNUNtRXhoZE5PZGt6a2dkWUpKMzlzNUpob2FRSWFRaHNrQk5DQTZPWFc1UWdqM1BkY3oydGFuUVR0UndQaW1ldlBDX2VPNUUzemRuU2ciLCJleHBpcmVzSW4iOjM1OTk5LCJpc3N1ZWRBdCI6MTc1MTcyMDk3NTk1MCwidHRsRXh0ZW5kZWRBdCI6MTc1MTcyMjQxODY0MCwibmFtZSI6Im11c2thbiBhZ2Fyd2FsIiwic2FmZUlkIjoiNWM1YzJhZjctYTU2Yy00ZDRkLWI2OGMtMDE3ZWY1OTJmOTU2IiwiYXBwTmFtZSI6Ik9SREVSSU5HIn0.jh_0SQXQLt4QAVD4t4M3MdTRxwPkQZ8jLqU1JsWeXFk; x_forwarded_host=mart.grab.com",
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    if response.status_code != 200:
        return None

    data = response.json()
    merchants = data.get("searchResult", {}).get("searchMerchants", [])

    result = []

    for m in merchants:
        result.append({
            "id": m.get("id", ""),
            "name": m.get("address", {}).get("name", ""),
            "photoUrl"  : m.get("merchantBrief", {}).get("photoHref", ""),
            "distanceInKm": m.get("merchantBrief", {}).get("distanceInKm", float('inf')),
            "rating": m.get("merchantBrief", {}).get("rating", 0),
            "estimatedDeliveryFee": m.get("estimatedDeliveryFee", {}).get("price", 0),
            "estimatedDeliveryTime": m.get("estimatedDeliveryTime", 0)
        })

   
    result_sorted = sorted(result, key=lambda x: x["distanceInKm"])
    return result_sorted[:5]

    
if __name__ == "__main__":
    mcp.run(transport="stdio")
